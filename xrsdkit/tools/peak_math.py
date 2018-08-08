import numpy as np
from scipy.special import wofz

from . import pearson

def peak_profile(q,q_pk,profile_name,params):
    if profile_name == 'voigt':
        hwhm_g = params['hwhm_g']
        hwhm_l = params['hwhm_l']
        line_shape = voigt(q-q_pk,hwhm_g,hwhm_l)
    elif profile_name == 'gaussian':
        hwhm_g = params['hwhm_g']
        line_shape = gaussian(q-q_pk,hwhm_g)
    elif profile_name == 'lorentzian':
        hwhm_l = params['hwhm_l']
        line_shape = lorentzian(q-q_pk,hwhm_l)
    return line_shape

def gaussian(x, hwhm_g):
    """
    gaussian (normal) distribution at points x, 
    center 0, half width at half max hwhm_g
    """
    return np.sqrt(np.log(2)/np.pi) / hwhm_g * np.exp(-(x/hwhm_g)**2 * np.log(2))

def lorentzian(x, hwhm_l):
    """
    lorentzian (cauchy) distribution at points x, 
    center 0, half width at half max hwhm_l
    """
    return hwhm_l / np.pi / (x**2+hwhm_l**2)

def voigt(x, hwhm_g, hwhm_l):
    """
    voigt distribution resulting from convolution 
    of a gaussian with hwhm hwhm_g 
    and a lorentzian with hwhm hwhm_l
    """
    sigma = hwhm_g / np.sqrt(2 * np.log(2))
    gamma = hwhm_l
    v = np.real(wofz((x+1j*gamma)/sigma/np.sqrt(2))) / sigma / np.sqrt(2*np.pi)
    return v 

def peaks_by_window(x,y,w=10,thr=0.):
    """Find peaks by comparing against neighboring values within a window.

    TODO: introduce window shapes and make use of the x-values.

    Parameters
    ----------
    x : array
        array of x-axis values
    y : array
        array of y-axis values
    w : int
        half-width of window- each point is analyzed
        with the help of this many points in either direction
    thr : float
        for a given point xi,yi, if yi is the maximum within the window,
        the peak is flagged if yi/mean(y_window)-1. > thr

    Returns
    -------
    pk_idx : list of int
        list of indices where peaks were found
    pk_confidence : list of float
        confidence in peak labeling for each peak found 
    """
    pk_idx = []
    pk_confidence = []
    for idx in range(w,len(y)-w-1):
        pkflag = False
        ywin = y[idx-w:idx+w+1]
        if np.argmax(ywin) == w:
            conf = ywin[w]/np.mean(ywin)-1.
            pkflag = conf > thr
        if pkflag:
            pk_idx.append(idx)
            pk_confidence.append(conf)
    return pk_idx,pk_confidence
   
def humpness(x,y,w=50):
    """Metric for hump-like and trough-like behavior in x,y data.

    Parameters
    ----------
    x : array
        array of x-axis values
    y : array
        array of y-axis values

    Returns
    -------
    humpness : array of float
        array of hump-like behavior metrics
    troughness : array of float
        array of trough-like behavior metrics
    """
    ny = len(y)
    humpness = np.zeros(ny)
    troughness = np.zeros(ny)
    for idx in range(ny):
        idx_lo = max([0,idx-w])
        idx_hi = min([ny,idx+w+1])
        ywin = y[idx_lo:idx_hi]
        xwin = x[idx_lo:idx_hi]
        pyx2 = pearson(ywin,(xwin-x[idx])**2) 
        humpness[idx] = -1*y[idx]*pyx2
        troughness[idx] = np.std(ywin)*pyx2

    #from matplotlib import pyplot as plt
    #plt.figure(10)
    #plt.plot(x,y)
    #plt.plot(x,humpness,'r')
    #plt.plot(x,troughness,'g')
    #plt.show()

    return humpness, troughness

