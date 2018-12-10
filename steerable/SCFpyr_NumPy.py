# MIT License
#
# Copyright (c) 2018 Tom Runia
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to conditions.
#
# Author: Tom Runia
# Date Created: 2018-12-04

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
from scipy.misc import factorial

import steerable.math_utils as math_utils
pointOp = math_utils.pointOp

################################################################################
################################################################################

class ComplexSteerablePyramid():

    def __init__(self, height, nbands):
        self._height = height  # including low-pass and high-pass
        self._nbands = nbands  # number of orientation bands
        self._coeff = [None]*self._height
    
    def set_level(self, level, coeff):
        self._coeff[level] = coeff
    
    def get_level(self, level):
        return self._coeff[level]

    def level_size(self, level):
        if level == 0:
            # High-pass
            return self._coeff[level].shape
        elif level == self._nbands:
            # Low-pass
            return self._coeff[level][0].shape
        # Intermediate levels
        return self._coeff[level][0].shape
        
################################################################################

class SCFpyr_NumPy():
    '''
    This is a modified version of buildSFpyr, that constructs a
    complex-valued steerable pyramid  using Hilbert-transform pairs
    of filters. Note that the imaginary parts will *not* be steerable.

    Description of this transform appears in: Portilla & Simoncelli,
    International Journal of Computer Vision, 40(1):49-71, Oct 2000.
    Further information: http://www.cns.nyu.edu/~eero/STEERPYR/

    Modified code from the perceptual repository:
      https://github.com/andreydung/Steerable-filter

    This code looks very similar to the original Matlab code:
      https://github.com/LabForComputationalVision/matlabPyrTools/blob/master/buildSCFpyr.m

    Also looks very similar to the original Python code presented here:
      https://github.com/LabForComputationalVision/pyPyrTools/blob/master/pyPyrTools/SCFpyr.py

    '''

    def __init__(self, height=5, nbands=4, scale_factor=2):
        self.nbands  = nbands  # number of orientation bands
        self.height  = height  # including low-pass and high-pass
        self.scale_factor = scale_factor
        
        # Cache constants
        self.lutsize = 1024
        self.Xcosn = np.pi * np.array(range(-(2*self.lutsize+1), (self.lutsize+2)))/self.lutsize
        self.alpha = (self.Xcosn + np.pi) % (2*np.pi) - np.pi


    ################################################################################
    # Construction of Steerable Pyramid

    def build(self, im):
        '''
        Build a complex steerable pyramid  with M 5 (incl. lowpass and highpass)
        Coeff is an array and subbands can be accessed as follows:
          HighPass:         coeff[0] : highpass
          BandPass Scale 1: coeff[1][0], coeff[1][1], coeff[1][2], coeff[1][3]
          BandPass Scale 2: coeff[2][0], coeff[2][1], coeff[2][2], coeff[2][3]
          ...
          LowPass: coeff[4]
        '''

        assert len(im.shape) == 2, 'Input im must be grayscale'
        height, width = im.shape

        # Check whether im shape allows the pyramid M
        max_height_pyr = int(np.floor(np.log2(min(width, height))) - 2)
        assert max_height_pyr >= self.height, 'Cannot buid pyramid heigher than {} levels'.format(max_height_pyr)
        
        # Prepare a grid
        log_rad, angle = math_utils.prepare_grid(height, width)

        # Radial transition function (a raised cosine in log-frequency):
        Xrcos, Yrcos = math_utils.rcosFn(1, -0.5)
        Yrcos = np.sqrt(Yrcos)

        YIrcos = np.sqrt(1 - Yrcos**2)

        lo0mask = pointOp(log_rad, YIrcos, Xrcos)
        hi0mask = pointOp(log_rad, Yrcos, Xrcos)

        # fftshift: Shift the zero-frequency component to the center of the spectrum.
        # Corresponds to the TensorFlow's fftshift function
        imdft = np.fft.fftshift(np.fft.fft2(im))

        # Low-pass
        lo0dft = imdft * lo0mask

        # Recursive build the steerable pyramid
        coeff = self._build_levels(lo0dft, log_rad, angle, Xrcos, Yrcos, self.height-1)

        # High-pass
        hi0dft = imdft * hi0mask
        hi0 = np.fft.ifft2(np.fft.ifftshift(hi0dft))

        print('#'*60)
        print('HIGH-PASS')
        print('  high-pass band, shape: {}'.format(hi0.real.shape))
        print('#'*60)

        # Note: high-pass is inserted in the beginning
        coeff.insert(0, hi0.real)

        # Convert to pyramid object
        pyr = ComplexSteerablePyramid(height=self.height, nbands=self.nbands)
        for level, level_coeff in enumerate(coeff):
            pyr.set_level(level, level_coeff)
            
        return pyr


    def _build_levels(self, lodft, log_rad, angle, Xrcos, Yrcos, height):
        '''
        Recursive function for constructing levels of a complex steerable pyramid. 
        This is called by buildSCFpyr, and is not usually called directly.
        '''

        print('#'*60)

        if height <= 1:

            # Low-pass
            print('LOW-PASS')
            lo0 = np.fft.ifft2(np.fft.ifftshift(lodft))
            coeff = [lo0.real]
            print('  low-pass band, shape: {}, type: {}'.format(lo0.real.shape, lo0.real.dtype))

        else:
            
            print('LEVEL {}'.format(height))
            Xrcos = Xrcos - 1

            ####################################################################
            ####################### Orientation bandpass #######################
            ####################################################################

            himask = pointOp(log_rad, Yrcos, Xrcos)

            order = self.nbands - 1
            const = np.power(2, 2*order) * np.square(factorial(order)) / (self.nbands * factorial(2*order))
            Ycosn = 2*np.sqrt(const) * np.power(np.cos(self.Xcosn), order) * (np.abs(self.alpha) < np.pi/2)

            # Loop through all orientation bands
            orientations = []
            for b in range(self.nbands):
                anglemask = pointOp(angle, Ycosn, self.Xcosn + np.pi*b/self.nbands)
                banddft = np.power(np.complex(0, -1), self.nbands - 1) * lodft * anglemask * himask
                band = np.fft.ifft2(np.fft.ifftshift(banddft))
                orientations.append(band)

            ####################################################################
            ######################## Subsample lowpass #########################
            ####################################################################

            dims = np.array(lodft.shape)

            # Both are tuples of size 2
            low_ind_start = (np.ceil((dims+0.5)/2) - np.ceil((np.ceil((dims-0.5)/2)+0.5)/2)).astype(int)
            low_ind_end   = (low_ind_start + np.ceil((dims-0.5)/2)).astype(int)
          
            # Selection
            log_rad = log_rad[low_ind_start[0]:low_ind_end[0], low_ind_start[1]:low_ind_end[1]]
            angle   = angle[low_ind_start[0]:low_ind_end[0], low_ind_start[1]:low_ind_end[1]]
            lodft   = lodft[low_ind_start[0]:low_ind_end[0], low_ind_start[1]:low_ind_end[1]]

            # Subsampling in frequency domain
            YIrcos = np.abs(np.sqrt(1 - Yrcos**2))
            lomask = pointOp(log_rad, YIrcos, Xrcos)
            lodft = lomask * lodft

            print('Lowpass:')
            print('  lodft', lodft.shape, lodft.dtype)

            ####################################################################
            ####################### Recursion next level #######################
            ####################################################################

            coeff = self._build_levels(lodft, log_rad, angle, Xrcos, Yrcos, height-1)
            coeff.insert(0, orientations)

        return coeff

    ################################################################################
    # Reconstruction to Image

    def reconstruct(self, coeff):

        if self.nbands != len(coeff[1]):
            raise Exception("Unmatched number of orientations")

        M, N = coeff[0].shape
        log_rad, angle = math_utils.prepare_grid(M, N)

        Xrcos, Yrcos = math_utils.rcosFn(1, -0.5)
        Yrcos  = np.sqrt(Yrcos)
        YIrcos = np.sqrt(np.abs(1 - Yrcos*Yrcos))

        lo0mask = pointOp(log_rad, YIrcos, Xrcos)
        hi0mask = pointOp(log_rad, Yrcos, Xrcos)

        tempdft = self._reconstruct_levels(coeff[1:], log_rad, Xrcos, Yrcos, angle)

        hidft = np.fft.fftshift(np.fft.fft2(coeff[0]))
        outdft = tempdft * lo0mask + hidft * hi0mask

        return np.fft.ifft2(np.fft.ifftshift(outdft)).real.astype(int)

    def _reconstruct_levels(self, coeff, log_rad, Xrcos, Yrcos, angle):

        if len(coeff) == 1:

            # Single level remaining, just perform Fourier transform
            return np.fft.fftshift(np.fft.fft2(coeff[0]))

        else:

            Xrcos = Xrcos - 1

            ####################################################################
            ####################### Orientation Residue ########################
            ####################################################################

            himask = pointOp(log_rad, Yrcos, Xrcos)

            lutsize = 1024
            Xcosn = np.pi * np.array(range(-(2*lutsize+1), (lutsize+2)))/lutsize
            order = self.nbands - 1
            const = np.power(2, 2*order) * np.square(factorial(order)) / (self.nbands * factorial(2*order))
            Ycosn = np.sqrt(const) * np.power(np.cos(Xcosn), order)

            orientdft = np.zeros(coeff[0][0].shape)

            for b in range(self.nbands):

                anglemask = pointOp(angle, Ycosn, Xcosn + np.pi * b/self.nbands)

                banddft = np.fft.fftshift(np.fft.fft2(coeff[0][b]))
                orientdft = orientdft + np.power(np.complex(0, 1), order) * banddft * anglemask * himask

            ####################################################################
            ########## Lowpass component are upsampled and convoluted ##########
            ####################################################################

            dims = np.array(coeff[0][0].shape)

            lostart = (np.ceil((dims+0.5)/2) -
                       np.ceil((np.ceil((dims-0.5)/2)+0.5)/2)).astype(np.int32)
            loend = lostart + np.ceil((dims-0.5)/2).astype(np.int32)

            nlog_rad = log_rad[lostart[0]:loend[0], lostart[1]:loend[1]]
            nangle = angle[lostart[0]:loend[0], lostart[1]:loend[1]]
            YIrcos = np.sqrt(np.abs(1 - Yrcos * Yrcos))
            lomask = pointOp(nlog_rad, YIrcos, Xrcos)

            nresdft = self._reconstruct_levels(coeff[1:], nlog_rad, Xrcos, Yrcos, nangle)
            resdft = np.zeros(dims, 'complex')
            resdft[lostart[0]:loend[0], lostart[1]:loend[1]] = nresdft * lomask

            return resdft + orientdft

