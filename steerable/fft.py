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
# Date Created: 2018-12-05

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import torch

################################################################################

def batch_flip_halves(x, axis):
    split = torch.chunk(x, 2, axis)
    return torch.cat((split[1], split[0]), dim=axis)

def batch_fftshift2d(x):
    assert isinstance(x, torch.Tensor), 'input must be a torch.Tensor'
    assert x.dim() == 4, 'input tensor must be of shape [N,H,W,2]'
    assert x.shape[-1] == 2, 'input tensor must be of shape [N,H,W,2]'
    ndim = x.dim()
    x = batch_flip_halves(x, axis=1)  # top,bottom
    x = batch_flip_halves(x, axis=2)  # left,right
    return x

def batch_ifftshift2d(x):
    ndim = x.dim()
    assert ndim == 4, 'input tensor must be of shape [N,H,W,2]'
    assert x.shape[-1] == 2, 'input tensor must be of shape [N,H,W,2]'
    x = batch_flip_halves(x, axis=2)  # left,right
    x = batch_flip_halves(x, axis=1)  # top,bottom
    return x

################################################################################
################################################################################

# def roll_n(X, axis, n):
#     # Source: https://github.com/locuslab/pytorch_fft/blob/master/pytorch_fft/fft/fft.py#L230
#     f_idx = tuple(slice(None, None, None) if i != axis else slice(0, n, None) for i in range(X.dim()))
#     b_idx = tuple(slice(None, None, None) if i != axis else slice(n, None, None) for i in range(X.dim()))
#     front = X[f_idx]
#     back = X[b_idx]
#     return torch.cat([back, front], axis)

# def fftshift(real, imag):
#     for dim in range(1, len(real.size())):
#         real = roll_n(real, axis=dim, n=real.size(dim)//2)
#         imag = roll_n(imag, axis=dim, n=imag.size(dim)//2)
#     return torch.stack((real, imag), -1)  # last dim=2 (real/imag)

# def ifftshift(real, imag):
#     for dim in range(len(real.size()) - 1, 0, -1):
#         real = roll_n(real, axis=dim, n=real.size(dim)//2)
#         imag = roll_n(imag, axis=dim, n=imag.size(dim)//2)
#     return torch.stack((real, imag), -1)  # last dim=2 (real/imag)