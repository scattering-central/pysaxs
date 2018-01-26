"""Modules for fitting a measured SAXS spectrum to a scattering equation."""
from __future__ import print_function
import warnings
from collections import OrderedDict
from functools import partial
import copy

import numpy as np
import lmfit

from . import saxs_math
from . import population_keys, parameter_keys

param_defaults = OrderedDict(
    I0_floor = 0.,
    G_gp = 1.E-3,
    rg_gp = 10.,
    D_gp = 4.,
    I0_sphere = 1.E-3,
    r0_sphere = 20.,
    sigma_sphere = 0.05,
    q_pkcenter=0.1,
    I_pkcenter=1.,
    pk_hwhm = 0.001)

param_limits = OrderedDict(
    I0_floor = (0.,10.),
    G_gp = (0.,1.E4),
    rg_gp = (1.E-6,1000.),
    D_gp = (0.,4.),
    I0_sphere = (0.,1.E4),
    r0_sphere = (1.,1000.),
    sigma_sphere = (0.,0.5),
    q_pkcenter = (0.,1.),
    I_pkcenter = (0.,1.E5),
    pk_hwhm = (1.E-6,1.E-1))

def update_params(p_old,p_new):
    for k,vals in p_new.items():
        npar = len(p_old[k])
        for i,val in enumerate(vals):
            if i < npar:
                p_old[k][i] = val
    return p_old

class SaxsFitter(object):
    """Container for handling SAXS spectrum parameter fitting."""

    def __init__(self,q_I,populations):
        """Initialize a SaxsFitter.

        Parameters
        ----------
        q_I : array
            n-by-2 array of scattering vectors q (1/Angstrom)
            and corresponding intensities (arbitrary units)
            against which the computed intensity will be compared
        populations : dict
            dict of the number of distinct populations 
            for each of the various scatterer types. 
            See saxs_math module documentation. 
        """
        self.populations = populations
        self.q = q_I[:,0]
        self.I = q_I[:,1]
        self.idx_fit = (self.I>0)
        self.logI = np.empty(self.I.shape)
        self.logI.fill(np.nan)
        self.logI[self.idx_fit] = np.log(self.I[self.idx_fit])

    def fit(self,params=None,fixed_params=None,param_limits=None,objective='chi2log'):
        """Fit the SAXS spectrum, optionally holding some parameters fixed.
    
        Parameters
        ----------
        params : dict
            Dict of scattering equation parameters (initial guess).
            If not provided, some defaults are chosen.
        fixed_params : dict, optional
            Dict of floats giving values in `params`
            that should be held constant during fitting.
            The structure of this dict should constitute
            a subset of the structure of the `params` dict.
            Entries in `fixed_params` take precedence 
            over the corresponding entries in `params`, so that the 
            initial condition does not violate the constraint.
            Entries in `fixed_params` that are outside 
            the structure of the `params` dict will be ignored.
        param_limits : dict, optional
            Like `fixed_params`, but containing tuples that define
            the upper and lower limits for fitting each parameter.
        objective : string
            Choice of objective function 
            (currently the only option is 'chi2log').

        Returns
        -------
        p_opt : dict
            Dict of optimized SAXS equation parameters,
            with the same shape as the input `params`.
        rpt : dict
            Dict reporting quantities of interest
            about the fit result.
        """

        if bool(self.populations['unidentified']):
            return OrderedDict(),OrderedDict()

        if params is None:
            params = self.default_params()

        #obj_init = self.evaluate(params)
        #print('obj_init: {}'.format(obj_init))

        lmf_params = self.lmfit_params(params,fixed_params,param_limits) 
        lmf_res = lmfit.minimize(self.lmf_evaluate,lmf_params,method='nelder-mead')
        p_opt = self.saxskit_params(lmf_res.params) 
        rpt = self.lmf_fitreport(lmf_res)
        
        obj_opt = self.evaluate(p_opt)
        #print(p_opt)
        #print('obj_opt: {}'.format(obj_opt))

        ####
        #I_init = saxs_math.compute_saxs(self.q,self.populations,params)
        #I_opt = saxs_math.compute_saxs(self.q,self.populations,p_opt)
        #from matplotlib import pyplot as plt
        #plt.figure(1)
        #plt.semilogy(self.q,self.I)
        #plt.semilogy(self.q,I_init,'r-')
        #plt.semilogy(self.q,I_opt,'g-')
        #plt.show()

        return p_opt,rpt

    def default_params(self):
        pkeys = []
        pd = OrderedDict()
        if bool(self.populations['unidentified']):
            return pd
        pd['I0_floor'] = [float(param_defaults['I0_floor'])]
        for p,v in self.populations.items():
            if bool(v):
                pkeys.extend(parameter_keys[p]) 
                for pk in parameter_keys[p]:
                    pd[pk] = [float(param_defaults[pk]) for i in range(v)]
        return pd

    def lmf_evaluate(self,lmf_params):
        return self.evaluate(self.saxskit_params(lmf_params))

    def evaluate(self,params):
        """Evaluate the objective for a given dict of params.

        Parameters
        ----------
        params : dict
            Dict of scattering equation parameters.

        Returns
        -------
        chi2log : float
            sum of difference squared of log(I) 
            between measured intensity and the 
            intensity computed from `param_dict`.
        """
        I_comp = saxs_math.compute_saxs(
            self.q,self.populations,params)
        #I_comp[I_comp<0.] = 1.E-12
        chi2log_total = saxs_math.compute_chi2(
                    np.log(I_comp[self.idx_fit]),
                    self.logI[self.idx_fit])
        #print('params: {}'.format(params))
        #print('chi2log: {}'.format(chi2log_total))
        #from matplotlib import pyplot as plt
        #plt.figure(1)
        #plt.semilogy(self.q,self.logI)
        #plt.semilogy(self.q,I_comp,'r-')
        #plt.show()
        return chi2log_total 

    def lmfit_params(self,params=None,fixed_params=None,param_bounds=None):
        # params
        p = self.default_params()
        if params is not None:
            p = update_params(p,params)
        # fixed params
        fp = self.default_params()
        for k,v in fp.items():
            for idx in range(len(v)):
                v[idx] = False
        if fixed_params is not None:
            fp = update_params(fp,fixed_params)
        # param bounds
        pb = self.default_params()
        for k,v in pb.items():
            for idx in range(len(v)):
                v[idx] = param_limits[k]
        if param_bounds is not None:
            pb = update_params(pb,param_bounds) 
        # lmfit 
        lmfp = lmfit.Parameters()
        for pkey,pvals in p.items():
            for i,val in enumerate(pvals):
                lmfp.add(pkey+str(i),value=val,vary=not fp[pkey][i],
                    min=pb[pkey][i][0],max=pb[pkey][i][1])
        return lmfp

    def saxskit_params(self,lmfit_params):
        p = self.default_params()
        for pkey,pvals in p.items():
            for validx,val in enumerate(pvals):
                p[pkey][validx] = lmfit_params[pkey+str(validx)].value
        return p

    def fit_intensity_params(self,params):
        """Fit the spectrum wrt only the intensity parameters."""
        fp = self.default_params()
        for k,v in fp.items():
            if k in ['I0_floor','I0_sphere','G_gp','I_pkcenter']:
                for idx in range(len(v)):
                    v[idx] = False
            else:
                for idx in range(len(v)):
                    v[idx] = True
        return self.fit(params,fp)


    def lmf_fitreport(self,lmf_result):
        rpt = OrderedDict()
        rpt['success'] = lmf_result.success
        fit_obj = self.lmf_evaluate(lmf_result.params)
        rpt['objective_value'] = fit_obj
        I_opt = saxs_math.compute_saxs(self.q,self.populations,
            self.saxskit_params(lmf_result.params)) 
        I_bg = self.I - I_opt
        snr = np.mean(I_opt)/np.std(I_bg) 
        rpt['fit_snr'] = snr
        return rpt 


## TODO: refactor this to new api.
#    def MC_anneal_fit(self,params,stepsize,nsteps,T,fixed_params=None):
#        """Perform a Metropolis-Hastings anneal for spectrum fit refinement.
#
#        Parameters
#        ----------
#        params : dict
#            Dict of scattering equation parameters (initial guess).
#            See saxs_math module documentation.
#        stepsize : float
#            fractional step size for random walk 
#        nsteps : int
#            Number of iterations to perform
#        T : float
#            Temperature employed in Metropolis acceptance decisions.
#        fixed_params : dict 
#            Dict indicating fixed values for `params`.
#            See documentation of SaxsFitter.fit().
#
#        Returns
#        -------
#        p_best : dict
#            Dict of best-fit parameters
#        p_current : dict
#            Dict of parameters obtained at the final iteration
#        rpt : dict
#            Report of objective function and Metropolis-Hastings results
#        """
#        u_flag = bool(self.populations['unidentified'])
#        pks_flag = bool(self.populations['diffraction_peaks'])
#        if u_flag or pks_flag: return OrderedDict(),OrderedDict(),OrderedDict()
#
#        # replace any params with the corresponding fixed_params
#        if fixed_params is not None:
#            for pname,pvals in fixed_params.items():
#                if pname in params.keys():
#                    for idx,val in enumerate(pvals):
#                        if idx < len(params[pname]):
#                            params[pname][idx] = val
#
#        fit_obj = self.evaluate
#        p_init = copy.deepcopy(params) 
#        p_current = copy.deepcopy(params) 
#        p_best = copy.deepcopy(params) 
#        obj_current = fit_obj(p_current)
#        obj_best = obj_current 
#        nrej = 0.
#
#        rpt = OrderedDict()
#        all_trials = range(nsteps)
#        for imc in all_trials:
#            # get trial params 
#            p_new = copy.deepcopy(p_current)
#            x_new,x_keys,param_idx = self.unpack_params(p_new) 
#            for idx in range(len(x_new)):
#                # TODO: check I0_floor, G_gp, and I0_sphere,
#                # to prevent amplitudes from going to zero
#                pfix = False
#                pkey = x_keys[idx]
#                if fixed_params is not None:
#                    if pkey in fixed_params.keys():
#                        paridx = x_keys[:idx].count(pkey)
#                        if paridx < len(fixed_params[pkey]):
#                            pfix = True
#                if not pfix:
#                    xi = x_new[idx]
#                    ki = x_keys[idx]
#                    param_range = param_limits[ki][1] - param_limits[ki][0]
#                    if xi == 0.:
#                        xi_trial = np.random.rand()*stepsize*param_range 
#                    else:
#                        xi_trial = xi*(1+2*(np.random.rand()-0.5)*stepsize)
#                    if xi_trial < param_limits[ki][0]:
#                        xi_trial = param_limits[ki][0] 
#                    if xi_trial > param_limits[ki][1]:
#                        xi_trial = param_limits[ki][1] 
#                    x_new[idx] = xi_trial 
#            p_new = self.pack_params(x_new,x_keys)
#            # evaluate objective, determine acceptance
#            obj_new = fit_obj(p_new)
#            if obj_new < obj_current:
#                accept = True
#                if obj_new < obj_best:
#                    p_best = p_new
#                    obj_best = obj_new
#            elif T == 0.:
#                accept = False
#            else:
#                accept = np.exp(-1.*(obj_new-obj_current)/T) > np.random.rand()
#            # act on acceptance decision
#            if accept:
#                p_current = p_new
#                obj_current = obj_new
#            else:
#                nrej += 1
#                p_new = p_current
#
#        rpt['reject_ratio'] = float(nrej)/nsteps
#        rpt['objective_init'] = fit_obj(p_init)
#        rpt['objective_best'] = fit_obj(p_best)
#        rpt['objective_final'] = fit_obj(p_current)
#        return p_best,p_current,rpt
#
#
