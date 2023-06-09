#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This is a python script that replicates the 
example_FreeSpacePropagation.m,
but by backtracking to before the focus at z=0, and trying to input a focusing beam.

It's a guassian beam of 30 um waist and the correct rayleigh range (~ 3.5 mm) propagating 
from z=0 to z=3 * (rayleigh range).

The workflow is a copy of Rob's LAPPLAC code, from matlab to python.
A combination of many scripts enough to replicate the example

Created on Wed Jul 9th 20:43:59 2020

Created by Cary Colgan, cary.colgan13@imperial.ac.uk
"""
#%%
import numpy as np
import matplotlib.pyplot as plt

import sys
if '../' not in sys.path: sys.path.append('../')   
from beamPropagator_source import *


#%%
# Setup Laser Parameters
# ----------------------
laserParameters = {
'lambda0' 	: 0.800*um,  	    # wavelength (m)
'tau'    	: 100.0*fs,	 	    # pulse width (s)
'E0'     	: 1.0,		  	# pulse energy (J)
'xOffset'	: 0.0*um,			# Spatial offset from center in x (m) - use at your own risk for the moment
'yOffset'	: 0.0*um,			# Spatial offset from center in y (m) - use at your own risk for the moment
'shape'  	: 'gaussian',
'n'          : 2,                         # n=2 is gaussian, n>2 is supergaussian
'w0'         : 30.0*um          #final waist size
}

# Define the beam profile and generate the beam 
# taken from generateInputBeam.m
# returns [x,y,z,inputBeam] 

zR = get_zr(laserParameters)
zMax   = 2.0*3.0*zR #(-3*zR to 3*zR)

zf = 3.0*zR #z point of focus

z0 = -zf  #relative to focal plane
Rz = z0 * (1.0 + (zR/z0)**2) #radius of curvature

w0 = laserParameters['w0']
w_z0 = w0 * np.sqrt(1.0 + (z0/zR)**2)

laserParameters['w_z0'] = w_z0
#%%
# Setup computational parameters
# ------------------------------
n_pts  = 512   		# number of pixels (must be even)
res    = 1*um   		# resolution in image plane (m)
nz     = 512    		# number of points in z (must be even)

mid = int(n_pts/2)
#%%
# Create calculation grid
# -----------------------
x = np.linspace(-res*n_pts/2 , res*n_pts/2, n_pts ) #centering occurs here
y = np.linspace(-res*n_pts/2 , res*n_pts/2, n_pts )
X, Y = np.meshgrid(x,y)
z = np.linspace(0,zMax,nz)


#get E field amplitude 
inputBeam = make_inputBeam(X,Y,laserParameters)

# Setup phase profile

# Define focusing beam
w_z0 = laserParameters['w_z0']
lambda0 = laserParameters['lambda0']

zR = np.pi*w0**2/(lambda0) #raylrigh range for guassian beam


k = 2.0*np.pi/lambda0
R_sq = X**2 + Y**2
guoy = np.arctan(z0/zR) #seems to have little, to no, effect?
inputPhase = k * R_sq/(2.0*Rz) - guoy

inputBeam = inputBeam * np.exp(-1j * inputPhase) #get it into complex format


# Check input beam and how this compares to waist size
fig, (ax1, ax2) = plt.subplots(1,2)
fig.suptitle('inputBeam')

extent = np.array([x.min(), x.max(), y.min(), y.max()])*1e6

ax1.set_title('|E|$^{2}$ Waist')
t = shadow(inputBeam)**2
ax1.imshow(t, extent=extent)


theta = np.linspace(0.0, 2.0*np.pi, 100)
r = w_z0 * 1e6
x_circ,y_circ = r*np.cos(theta), r*np.sin(theta)
ax1.plot(x_circ,y_circ,'r')


ax2.set_title('Phase')
ax2.imshow(phase(inputBeam), extent=extent)


#%%
# Specify plasma
# --------------
# None - propagate in vacuum
ne = np.zeros((n_pts, n_pts, nz))

#%%
# Setup first step and tools for propagation
# -----------------------------------------
# Propagate the beam through the plasma structure
# data.Field = beamPropagator(data); 

# Absorbing boundaries
# Reduces the effect of the edges of the domain
absorbingBoundaries = 1

eta0 = 1.0

eta = eta0 * np.ones((n_pts,n_pts,z.size))  #has to be for free-space
k0 = 2.0*np.pi/laserParameters['lambda0']

AS, xFreq, yFreq, G, mask, X, Y, z, eta = setup_propagate(inputBeam, X, Y, z, eta, k0, eta0, absorbingBoundaries)

#%%
# Main iteration loop in dz
# -------------------------

# can be quite slow
Field = propagate_in_z(AS, xFreq, yFreq, G, mask, X, Y, z, eta, k0)

#%%
# Interactive viewer of whole propagation of beam
# -----------------------------------------------

buttons = explorer(Field, ne, z)

#%%
# Compare with Gaussian beam propagation theory
# ---------------------------------------------

fig, (ax1, ax2, ax3) = plt.subplots(1, 3, sharex=True, sharey=True)

fig.suptitle('Gaussian Free Space Propagation')

asp = (z.max() - z.min()) / (y.max()  - y.min())
ax1.imshow(shadow(Field[:, mid, :]), aspect=asp, extent=[z.min()*1e3, z.max()*1e3, y.min()*1e3, y.max()*1e3])

im = phase(Field[:, mid, :])
ax2.imshow(im, aspect=asp, extent=[z.min()*1e3, z.max()*1e3, y.min()*1e3, y.max()*1e3],
           cmap=matplotlib.cm.RdBu_r, 
           norm=MidpointNormalize(midpoint=0.0,vmin=-np.pi/2.0, vmax=np.pi/2.0))


# Check phase does go from negative to positive through focus
Zd,Yd = np.meshgrid(z*1e3, y*1e3)
levels = np.linspace(-np.pi/2.0, np.pi/2.0, 9)
ax2.contour(Zd, Yd, im, levels=levels)

ax1.set_xlabel('z (mm)')
ax1.set_ylabel('y (mm)')
ax2.set_xlabel('z (mm)')
ax3.set_xlabel('z (mm)')

# threshold beam propagation at e**-2 value to compare with analytical theory
# of waist size propagation
thresh = np.zeros_like(Field[:, mid, :], dtype=np.float64)
for zi in range((Field.shape[-1])):
    f = Field[:,mid,zi].copy()
    f = np.abs(f)**2
    top = np.max(f)
    f[f <= top*np.e**(-2)] = 0.0
    f[f > top*np.e**(-2)] = 1.0
    thresh[:,zi] = f

# Analytical formula - overlay on plot
w0 *= 1.00
zR = np.pi*w0**2/(lambda0)
zf = 3.0*zR
zc = z.copy() - zf
w = w0 * np.sqrt(1.0 + (zc/zR)**2)        
ax3.imshow(thresh, aspect=asp, extent=[z.min()*1e3, z.max()*1e3, y.min()*1e3, y.max()*1e3])
ax3.plot(z*1e3, w*1e3, 'r--', label='Analytical')
ax3.plot(z*1e3, -w*1e3, 'r--')

ax1.set_title('$|E|$')
ax2.set_title('Phase')
ax3.set_title('$|E|^2$')
ax3.legend()


#%%
# Check that we get negative and positive curved wavefronts in real space
# Requires adding back in the exp(-j * omega * t) factor
# ------------------------------------------------------
plt.figure()

E_full = np.real(np.exp(+1j * k0 * Zd*1e-3) *  Field[:, mid, :])
plt.imshow(E_full, aspect=asp, extent=[z.min()*1e3, z.max()*1e3, y.min()*1e3, y.max()*1e3])

plt.title('Include Beam Oscillations: $\Re$(Ee$^{ikz}$)')
plt.xlabel('z (mm)')
plt.ylabel('y (mm)')


#%%
# Compare focal spot to Gaussian beam propagation theory
# -----------------------------------------------------

# Find focal point in z
idx = np.argmin((z-zf)**2)
focal_slice = Field[:,:,idx].copy()

# Get beam intensity at this position
I = shadow(focal_slice)
e2_val = I.max()*np.exp(-2)

extent = np.array([x.min(), x.max(), y.min(), y.max()])*1e6

plt.figure()
plt.title('Intensity at Focus')
plt.imshow(I, cmap='viridis', 
           extent=extent)
ax = plt.gca()
CS = ax.contour(1e6*X, 1e6*Y, I, levels=[e2_val], colors=['y'])
ax.clabel(CS, CS.levels, inline=True, fmt='$1/e^{2}$', fontsize=10)

plt.xlabel('x [$\mu$m]')
plt.ylabel('y [$\mu$m]')

# Compare to theoretial focal spot size
# Very good agreement
theta = np.linspace(0.0, 2.0*np.pi, 100)
r = w0 * 1e6
x_circ,y_circ = r*np.cos(theta), r*np.sin(theta)
plt.plot(x_circ,y_circ,'r', label='Theoretical focal spot')
plt.legend()