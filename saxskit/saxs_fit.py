"""Modules for fitting a measured SAXS spectrum to a scattering equation."""
from __future__ import print_function
import warnings
from collections import OrderedDict
from functools import partial
import copy

from . import saxs_math

import numpy as np
from scipy.optimize import minimize as scipimin

# parameter limits for fit_spectrum() and MC_anneal_fit():
param_limits = OrderedDict(
    I0_floor = (0.,10.),
    G_gp = (0.,1.E4),
    rg_gp = (1E-6,1.E3),
    D_gp = (0.,4.),
    I0_sphere = (0.,1.E4),
    r0_sphere = (1E-6,1.E3),
    sigma_sphere = (0.,0.5))

class SaxsFitter(object):

    def __init__(self,populations,q_I,q_range=None):
        self.populations = populations
        self.q = q_I[:,0]
        self.I = q_I[:,1]
        # the following log operation may throw a warning- it's ok.
        # any resulting zeros and nans will not be used.
        self.logI = np.log(self.I)
        self.q_range = q_range
        if self.q_range is not None:
            self.idx_fit = ((self.I>0)
                &(self.q>self.q_range[0])
                &(self.q<self.q_range[1]))
        else:
            self.idx_fit = (I>0)

    def evaluate(self,param_array):
        """param_array should have been generated by self.unpack_params()"""
        param_dict = self.pack_params(test_params)
        I_comp = saxs_math.compute_saxs(self.q,self.populations,param_dict)
        chi2log_total = 0
        for pkey in self.populations.keys():
            if pkey == 'guinier_porod':
                # weight the high-q region 
                chi2log = compute_chi2(I_comp[self.idx_fit],self.logI[idx_fit],self.q)
            if pkey == 'spherical_normal':
                # weight the low-q region
                chi2log = compute_chi2(I_comp[self.idx_fit],self.logI[idx_fit],self.q[::-1])
            #if pkey == 'diffraction_peaks':
            #    chi2log = 0
            #    # window the region surrounding this peak
            #    # idx_pk = ...
            #    for ipk in range(int(self.populations['diffraction_peaks'])):
            #        # get q range of the peak
            #        # evaluate objective
            #        chi2log += compute_chi2(I_comp[(idx_pk&idx_fit)],self.logI[(idx_pk&idx_fit)])
            chi2log_total += chi2log
        return chi2log 

    def pack_params(self,param_array):
        param_dict = OrderedDict()
        param_dict['I0_floor'] = param_array[0]
        idx = 1
        for pkey in self.populations.keys():
            param_dict[pkey] = []
            for ipop in range(int(self.populations[pkey])):
                param_dict['pkey'].append(param_array[idx])
                idx += 1
        return param_dict

    def unpack_params(self,param_dict):
        param_list = []
        if 'I0_floor' in param_dict:
            param_list.append(param_dict['I0_floor'])
        for pkey in self.populations.keys():
            if pkey in param_dict:
                if not isinstance(param_dict[pkey],list):
                    param_list.append(param_dict[pkey])
                else:
                    param_list.extend(param_dict[pkey])
        return np.array(param_list)

    def fit(self,params,fixed_params):
        pass
    # index the params into an array 
    #params = OrderedDict(params)
    #x_init = np.zeros(len(params))
    #x_bounds = [] 
    #p_idx = OrderedDict() 
    #I_idx = OrderedDict() 
    #for i,k in zip(range(len(params)),params.keys()):
    #    p_idx[k] = i 
    #    x_init[i] = params[k]
    #    if k in ['G_precursor','I0_floor','I0_sphere']:
    #        I_idx[k] = i
    #    x_bounds.append(param_limits[k])
    #    #if k in ['rg_precursor','r0_sphere']:
    #    #    x_bounds.append((1E-3,None))
    #    #elif k in ['G_precursor','I0_sphere','I0_floor']:
    #    #    x_bounds.append((0.0,None))
    #    #elif k in ['sigma_sphere']:
    #    #    x_bounds.append((0.0,1.0))
    #    #else:
    #    #    x_bounds.append((None,None))
   
    # --- constraints --- 
    #c = []
    #if objective in ['chi2log_fixI0']:
    #    if len(I_idx) > 0:
    #        # Set up a constraint to keep I(q=0) fixed
    #        I0_init = np.sum([x_init[i] for i in I_idx.values()])
    #        cfun = lambda x: np.sum([x[I_idx[k]] for k in I_idx.keys()]) - I0_init
    #        c.append({'type':'eq','fun':cfun})
    #for fixk in fixed_params:
    #    cfun = lambda x: x[p_idx[fixk]] - params[fixk]
    #    c.append({'type':'eq','fun':cfun})
    # --- end constraints ---

    #p_opt = copy.deepcopy(params) 
    #fit_obj = saxs_chi2log(flags,params,q_I)
    #rpt = OrderedDict()
    #res = scipimin(fit_obj,x_init,
    #    bounds=x_bounds,
    #    options={'ftol':1E-3},
    #    constraints=c)
    #for k,xk in zip(params.keys(),res.x):
    #    p_opt[k] = xk
    #rpt['fixed_params'] = fixed_params
    #rpt['objective'] = objective 
    #rpt['objective_value'] = fit_obj(res.x)
    #I_opt = compute_saxs(q,flags,p_opt) 
    #I_bg = I - I_opt
    #snr = np.mean(I_opt)/np.std(I_bg) 
    #rpt['fit_snr'] = snr

    #I_opt = compute_saxs(q,flags,p_opt) 
    #I_guess = compute_saxs(q,flags,params) 
    #from matplotlib import pyplot as plt
    #plt.figure(2)
    #plt.plot(q,I)
    #plt.plot(q,I_guess,'r')
    #plt.plot(q,I_opt,'g')
    #plt.figure(12)
    #plt.semilogy(q,I)
    #plt.semilogy(q,I_guess,'r')
    #plt.semilogy(q,I_opt,'g')
    #print('flags: \n{}'.format(flags))
    #plt.show()


def saxs_chi2log(populations,params,q_I):
    """Return a function that evaluates saxs intensity fit error.

    Parameters
    ----------
    populations : dict
        dict of the number of distinct populations 
        for each of the various scatterer types. 
        See saxs_math module documentation. 
    params : dict
        dict of scattering equation parameters.
        See saxs_math module documentation.
    q_I : array
        n-by-2 array of scattering vectors q (1/Angstrom)
        and corresponding intensities (arbitrary units)
        against which the computed intensity will be compared

    Returns
    -------
    fit_obj : function
        an anonymous function to be used 
        as a saxs intensity fitting objective

    See Also
    --------
    saxs_math.compute_saxs 
    """
    saxs_fitter = SaxsFitter(populations,q_I)
    return saxs_fitter.evaluate

def MC_anneal_fit(q_I,populations,params,stepsize,nsteps,T):
    """Perform a Metropolis-Hastings iteration for spectrum fit refinement.

    Parameters
    ----------
    q_I : array
        n-by-2 array of intensity (arb) versus scattering vector (1/Angstrom)
    populations : dict
        Dict of scattering population flags. 
        See saxs_math module documentation.
    params : dict
        Dict of scattering equation parameters (initial guess).
        See saxs_math module documentation.
    stepsize : float
        fractional step size for random walk 
    nsteps : int
        Number of iterations to perform
    T : float
        Temperature employed in Metropolis acceptance decisions.

    Returns
    -------
    p_best : dict
        Dict of best-fit parameters
    p_fin : dict
        Dict of parameters obtained at the final iteration
    rpt : dict
        Report of objective function and Metropolis-Hastings results
    """
    u_flag = bool(populations['unidentified'])
    pks_flag = bool(populations['diffraction_peaks'])
    if u_flag or pks_flag: return OrderedDict(),OrderedDict(),OrderedDict()

    fit_obj = saxs_chi2log(populations,params,q_I) 
    p_init = copy.deepcopy(params) 
    p_current = copy.deepcopy(params) 
    p_best = copy.deepcopy(params) 
    obj_current = fit_obj(p_current.values())
    obj_best = obj_current 
    nrej = 0.

    rpt = OrderedDict()
    all_trials = range(nsteps)
    for imc in all_trials:
        # get trial params 
        p_new = copy.deepcopy(p_current)
        for k,v in p_new.items():
            param_range = param_limits[k][1] - param_limits[k][0]
            if v == 0.:
                p_trial = np.random.rand()*stepsize*param_range 
            else:
                p_trial = v*(1+2*(np.random.rand()-0.5)*stepsize)
            if p_trial < param_limits[k][0]:
                p_trial = param_limits[k][0] 
            if p_trial > param_limits[k][1]:
                p_trial = param_limits[k][1] 
            p_new[k] = p_trial 
        # evaluate objective, determine acceptance
        obj_new = fit_obj(p_new.values())
        if obj_new < obj_current:
            accept = True
            if obj_new < obj_best:
                p_best = p_new
                obj_best = obj_new
        elif T == 0:
            accept = False
        else:
            accept = np.exp(-1.*(obj_new-obj_current)/T) > np.random.rand()
        # act on acceptance decision
        if accept:
            p_current = p_new
            obj_current = obj_new
        else:
            nrej += 1
            p_new = p_current

    rpt['reject_ratio'] = float(nrej)/nsteps
    rpt['objective_init'] = fit_obj(p_init.values())
    rpt['objective_best'] = fit_obj(p_best.values())
    rpt['objective_final'] = fit_obj(p_current.values())

    return p_best,p_current,rpt


def fit_spectrum(q_I,populations,params,fixed_params=None,objective='chi2log'):
    """Fit a SAXS spectrum, given population flags and parameter guesses.

    Parameters
    ----------
    q_I : array
        n-by-2 array of scattering vector q (1/Angstrom) and intensity.
    populations : dict
        Dict of scattering population flags. 
        See saxs_math module documentation.
    params : dict
        Dict of scattering equation parameters (initial guess).
        See saxs_math module documentation.
    fixed_params : dict 
        Dict indicating which parameters to hold fixed during optimization.
        Single parameters are held fixed by setting the dict entry to True.
        If multiple populations of a given type are included
        (i.e. if the corresponding entry in `params` is a list)
        then the value in `fixed_params` should be a list of booleans
        where only the True-valued entries will be held fixed.
    objective : str
        choice of objective function for the fitting. supported objectives:
        - 'chi2log': sum of difference of logarithm, squared, across entire q range. 
        - 'chi2log_fixI0': like chi2log, but with I(q=0) constrained. 

    Returns
    -------
    p_opt : dict
        Dict of scattering equation parameters 
        optimized to fit `q_I` under `objective`.
    rpt : dict
        Dict reporting objective function and its values
        at the initial and final points 
    """
    u_flag = bool(populations['unidentified'])
    pks_flag = bool(populations['diffraction_peaks'])
    if u_flag or pks_flag: return OrderedDict(),OrderedDict()

    saxs_fitter = SaxsFitter(populations,q_I)
    p_opt, rpt = saxs_fitter.fit(params,fixed_params)

    return p_opt,rpt


#def precursor_heuristics(q_I):
#    """Guess radius of gyration and Guinier prefactor of scatterers.
#
#    Parameters
#    ----------
#    q_I : array
#        n-by-2 array of q (scattering vector magnitude) 
#        and I (intensity at q)
#
#    Returns
#    -------
#    rg_pre : float
#        estimated radius of gyration 
#    G_pre : float
#        estimated Guinier factor
#    """
#    n_q = len(q_I[:,0])
#    ## use the higher-q regions 
#    highq_I = q_I[int(n_q*1./2):,:] 
#    #highq_I = q_I[int(n_q*3./4):,:] 
#    fit_obj = lambda x: fit_guinier_porod(highq_I,x[0],4,x[1])
#    idx_nz = highq_I[:,1]>0
#    res = scipimin(fit_obj,[1,1],bounds=[(1E-3,10),(1E-3,None)])
#    rg_opt, G_opt = res.x
#    I_pre = guinier_porod(q_I[:,0],rg_opt,4,G_opt)
#    return rg_opt, G_opt

#def fit_guinier_porod(q_I,rg,porod_exp,G):
#    Igp = guinier_porod(q_I[:,0],rg,porod_exp,G)
#    return np.sum( (q_I[:,1]-Igp)**2 )

#def spherical_normal_heuristics(q_I,I_at_0):
#    """Guess mean and std of radii for spherical scatterers.
#
#    This algorithm was developed and 
#    originally contributed by Amanda Fournier.    
#
#    Performs some heuristic measurements on the input spectrum,
#    in order to make educated guesses 
#    for the parameters of a size distribution
#    (mean and standard deviation of radius)
#    for a population of spherical scatterers.
#
#    TODO: Document algorithm here.
#    """
#    m = saxs_Iq4_metrics(q_I)
#
#    width_metric = m['pI_qwidth']/m['q_at_Iqqqq_min1']
#    intensity_metric = m['I_at_Iqqqq_min1']/I_at_0
#    #######
#    #
#    # The function spherical_normal_heuristics_setup()
#    # (in this same module) should be used to regenerate these polynomials
#    # if any part of saxs_Iq4_metrics() is changed.
#    # polynomial coefs for qr0 focus: 
#    p_f = [16.86239254,8.85709143,-11.10439599,-0.26735688,4.49884714]
#    # polynomial coefs for width metric: 
#    p_w = [12.42148677,-16.85723287,7.43401497,-0.38234993,0.06203096]
#    # polynomial coefs for intensity metric: 
#    p_I = [1.19822603,-1.20386273,2.88652860e-01,1.78677430e-02,-2.67888841e-04]
#    #
#    #######
#    # Find the sigma_r/r0 value that gets the extracted metrics
#    # as close as possible to p_I and p_w.
#    width_error = lambda x: (np.polyval(p_w,x)-width_metric)**2
#    intensity_error = lambda x: (np.polyval(p_I,x)-intensity_metric)**2
#    # TODO: make the objective function weight all errors equally
#    heuristics_error = lambda x: width_error(x) + intensity_error(x)
#    res = scipimin(heuristics_error,[0.1],bounds=[(0,0.45)]) 
#    sigma_over_r = res.x[0]
#    qr0_focus = np.polyval(p_f,sigma_over_r)
#    # qr0_focus = x1  ==>  r0 = x1 / q1
#    r0 = qr0_focus/m['q_at_Iqqqq_min1']
#    return r0,sigma_over_r


#def compute_saxs_with_substitutions(q,populations,params,param_array):
#    subs_params = copy.deepcopy(params)
#    ipar = 0
#    for k in subs_params.keys():
#        if isinstance(subs_params[k],list):
#            for ipop in range(len(subs_params[k])):
#                subs_params[k][ipop] = param_array[ipar]
#                ipar += 1
#        else:
#            subs_params[k] = param_array[ipar] 
#            ipar += 1
#    return compute_saxs(q,populations,subs_params)

#def spherical_normal_heuristics_setup():
#    sigma_over_r = []
#    width_metric = []
#    intensity_metric = []
#    qr0_focus = []
#    # TODO: replace this with a sklearn model 
#    r0 = 10
#    q = np.arange(0.001/r0,float(20)/r0,0.001/r0)       #1/Angstrom
#    # NOTE: algorithm works for sigma/r up to 0.45
#    sigma_r_vals = np.arange(0*r0,0.46*r0,0.01*r0)      #Angstrom
#    for isig,sigma_r in zip(range(len(sigma_r_vals)),sigma_r_vals):
#        I = spherical_normal_saxs(q,r0,sigma_r/r0) 
#        print('getting I*q**4 metrics for sigma_r/r0 = {}'.format(sigma_r/r0))
#        d = saxs_Iq4_metrics(np.array(zip(q,I)))
#        sigma_over_r.append(float(sigma_r)/r0)
#        qr0_focus.append(d['q_at_Iqqqq_min1']*r0)
#        width_metric.append(d['pI_qwidth']/d['q_at_Iqqqq_min1'])
#        I_at_0 = spherical_normal_saxs(np.array([0]),r0,sigma_r/r0)[0] 
#        intensity_metric.append(d['I_at_Iqqqq_min1']/I_at_0)
#    p_f = np.polyfit(sigma_over_r,qr0_focus,4,None,False,None,False)
#    p_w = np.polyfit(sigma_over_r,width_metric,4,None,False,None,False)
#    p_I = np.polyfit(sigma_over_r,intensity_metric,4,None,False,None,False)
#    print('polynomial coefs for qr0 focus: {}'.format(p_f))
#    print('polynomial coefs for width metric: {}'.format(p_w))
#    print('polynomial coefs for intensity metric: {}'.format(p_I))
#    plot = True
#    if plot: 
#        from matplotlib import pyplot as plt
#        plt.figure(1)
#        plt.scatter(sigma_over_r,width_metric)
#        plt.plot(sigma_over_r,np.polyval(p_w,sigma_over_r))
#        plt.figure(2)
#        plt.scatter(sigma_over_r,intensity_metric)
#        plt.plot(sigma_over_r,np.polyval(p_I,sigma_over_r))
#        plt.figure(3)
#        plt.scatter(sigma_over_r,qr0_focus)
#        plt.plot(sigma_over_r,np.polyval(p_f,sigma_over_r))
#        plt.figure(4)
#        plt.scatter(width_metric,intensity_metric) 
#        plt.show()
#


