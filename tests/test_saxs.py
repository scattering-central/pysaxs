from __future__ import print_function
import os
import glob
from collections import OrderedDict

import numpy as np

from saxskit import saxs_math, saxs_fit, saxs_classify, saxs_regression
from saxskit import peak_math

from citrination_client import CitrinationClient
from saxskit.saxs_models import get_data_from_Citrination
from saxskit.saxs_models import train_classifiers, train_regressors
from saxskit.saxs_models import train_classifiers_partial, train_regressors_partial
from saxskit.saxs_models import save_models

from saxskit.saxs_math import profile_spectrum
from saxskit.saxs_citrination import CitrinationSaxsModels

def test_guinier_porod():
    qvals = np.arange(0.01,1.,0.01)
    Ivals = saxs_math.guinier_porod(qvals,20,4,120)

def test_spherical_normal_saxs():
    qvals = np.arange(0.01,1.,0.01)
    Ivals = saxs_math.spherical_normal_saxs(qvals,20,0.2)
    Ivals = saxs_math.spherical_normal_saxs(qvals,20,0.)

def test_diffraction_peaks():
    qvals = np.arange(0.01,1.,0.01)
    Ivals = peak_math.voigt(qvals-0.5,0.05,0.05)

def test_profile_spectrum():
    datapath = os.path.join(os.path.dirname(__file__),
        'test_data','solution_saxs','precursors','precursors_0.csv')
    test_data = open(datapath,'r')
    q_I_gp = np.loadtxt(test_data,dtype=float,delimiter=',')
    prof = saxs_math.profile_spectrum(q_I_gp)
    gp_prof = saxs_math.guinier_porod_profile(q_I_gp)
    gp_pops = OrderedDict.fromkeys(saxs_fit.population_keys)
    gp_pops.update({'guinier_porod':1})

    datapath = os.path.join(os.path.dirname(__file__),
        'test_data','solution_saxs','spheres','spheres_0.csv')
    test_data = open(datapath,'r')
    q_I_sph = np.loadtxt(test_data,dtype=float,delimiter=',')
    prof = saxs_math.profile_spectrum(q_I_sph)
    sph_prof = saxs_math.spherical_normal_profile(q_I_sph)
    sph_pops = OrderedDict.fromkeys(saxs_fit.population_keys)
    sph_pops.update({'spherical_normal':1})

    datapath = os.path.join(os.path.dirname(__file__),
        'test_data','solution_saxs','peaks','peaks_0.csv')
    test_data = open(datapath,'r')
    q_I_pks = np.loadtxt(test_data,dtype=float,delimiter=',')
    prof = saxs_math.profile_spectrum(q_I_pks)
    #pks_prof = saxs_math.diffraction_peak_profile(q_I_pks)
    pks_pops = OrderedDict.fromkeys(saxs_fit.population_keys)
    pks_pops.update({'diffraction_peaks':1})

    pops = OrderedDict.fromkeys(saxs_fit.population_keys)
    pops.update(gp_pops)
    pops.update(sph_pops)
    pops.update(pks_pops)

    I_tot = q_I_gp[:,1] + q_I_sph[:,1] + q_I_pks[:,1]
    q_I_tot = np.vstack([q_I_gp[:,1],I_tot]).T
    pop_profs = saxs_math.detailed_profile(q_I_tot,pops)

def test_classifier():
    model_file_path = os.path.join(os.getcwd(),'saxskit','modeling_data','scalers_and_models.yml')
    sxc = saxs_classify.SaxsClassifier(model_file_path)
    for data_type in ['precursors','spheres','peaks']:
        data_path = os.path.join(os.getcwd(),'tests','test_data','solution_saxs',data_type)
        data_files = glob.glob(os.path.join(data_path,'*.csv'))
        for fpath in data_files:
            print('testing classifier on {}'.format(fpath))
            q_I = np.loadtxt(fpath,delimiter=',')
            prof = saxs_math.profile_spectrum(q_I)
            pops,certs = sxc.classify(prof)
            for popk in pops.keys():
                print('\t{} populations: {} ({} certainty)'.format(popk,pops[popk],certs[popk]))

def test_regressions():
    model_file_path = os.path.join(os.getcwd(),'saxskit',
        'modeling_data','scalers_and_models.yml')
    model_file_path_reg = os.path.join(os.getcwd(),'saxskit',
        'modeling_data','scalers_and_models_regression.yml')
    sxc = saxs_classify.SaxsClassifier(model_file_path)
    sxr = saxs_regression.SaxsRegressor(model_file_path_reg)
    for data_type in ['precursors','spheres','peaks']:
        data_path = os.path.join(os.getcwd(),'tests','test_data','solution_saxs',data_type)
        data_files = glob.glob(os.path.join(data_path,'*.csv'))
        for fpath in data_files:
            print('testing regression on {}'.format(fpath))
            q_I = np.loadtxt(fpath,delimiter=',')
            prof = saxs_math.profile_spectrum(q_I)
            pops,certs = sxc.classify(prof)
            params = sxr.predict_params(pops,prof,q_I)
            for k, v in params.items():
                print('\t{} parameter: {} '.format(k,v))

def test_fitter():
    datapath = os.path.join(os.path.dirname(__file__),
        'test_data','solution_saxs','spheres','spheres_0.csv')
    print('testing SaxsFitter on {}'.format(datapath))
    #datapath = os.path.join(os.path.dirname(__file__),
    #    'test_data','solution_saxs','peaks','peaks_0.csv')
    test_data = open(datapath,'r')
    q_I = np.loadtxt(test_data,dtype=float,delimiter=',')
    model_file_path = os.path.join(os.getcwd(),'saxskit',
        'modeling_data','scalers_and_models.yml')
    model_file_path_reg = os.path.join(os.getcwd(),'saxskit',
        'modeling_data','scalers_and_models_regression.yml')
    sxc = saxs_classify.SaxsClassifier(model_file_path)
    prof = saxs_math.profile_spectrum(q_I)
    pops,certs = sxc.classify(prof)
    sxr = saxs_regression.SaxsRegressor(model_file_path_reg)
    params = sxr.predict_params(pops,prof,q_I)
    sxf = saxs_fit.SaxsFitter(q_I,pops)
    params,rpt = sxf.fit_intensity_params(params)
    p_opt,rpt_opt = sxf.fit(params)
    obj_init = sxf.evaluate(params)
    obj_opt = sxf.evaluate(p_opt)
    print('optimization objective: {} --> {}'.format(obj_init,obj_opt))
    for k, v in params.items():
        print('\t{}: {} --> {}'.format(k,v,p_opt[k]))

def test_model_training():
    path = os.getcwd()
    head, tail = os.path.split(path)
    api_key_file = os.path.join(head, 'api_key.txt')
    if not os.path.exists(api_key_file):
        return
    with open(api_key_file, "r") as g:
        a_key = g.readline().strip()
    cl = CitrinationClient(site='https://slac.citrination.com',api_key=a_key)

    data = get_data_from_Citrination(client=cl, dataset_id_list=[16])
    data_len = data.shape[0]

    train = data.iloc[:int(data_len*0.9),:]
    train_part = data.iloc[int(data_len*0.9):,:]

    p = os.path.abspath(__file__)
    d = os.path.dirname(os.path.dirname(p))
    test_classifiers_path = os.path.join(d,'saxskit','modeling_data','test_classifiers.yml')
    test_regressors_path = os.path.join(d,'saxskit','modeling_data','test_regressors.yml')
    
    scalers, models, accuracy = train_classifiers(train, hyper_parameters_search=False, model='all')
    save_models(scalers, models, accuracy, test_classifiers_path)

    scalers, models, accuracy = train_regressors(train, hyper_parameters_search=False, model='all')
    save_models(scalers, models, accuracy, test_regressors_path)

    scalers, models, accuracy = train_classifiers_partial(
        train_part, test_classifiers_path, all_training_data=data, model='all')
    save_models(scalers, models, accuracy, test_classifiers_path)

    scalers, models, accuracy = train_regressors_partial(
        train_part, test_regressors_path, all_training_data=data, model='all')
    save_models(scalers, models, accuracy, test_regressors_path)

def test_citrination_models():
    path = os.getcwd()
    head, tail = os.path.split(path)
    api_key_file = os.path.join(head, 'api_key.txt')
    if not os.path.exists(api_key_file):
        return

    test_path = os.path.join(head,'saxskit','examples','sample_0.csv')
    q_i = np.genfromtxt (test_path, delimiter=",")
    features = profile_spectrum(q_i)


    saxs_models = CitrinationSaxsModels(api_key_file,'https://slac.citrination.com')
    print('testing Citrination models on {}'.format(test_path))

    flags, uncertainties = saxs_models.classify(features)
    print("scatterer populations: ")
    for popk in flags.keys():
        print('\t{} populations: {} ({} certainty)'.format(popk,flags[popk],uncertainties[popk]))

    params,uncertainties = saxs_models.predict_params(flags, features, q_i)
    print("scattering and intensity parameters: ")
    for popk in params.keys():
        print('\t{} populations: {} ({} certainty)'.format(popk,params[popk],uncertainties[popk]))


#def test_citrination_classifier(address,api_key_file):
#    model_file_path = os.path.join(os.getcwd(),'saxskit','modeling_data','scalers_and_models.yml')
#    sxc = saxs_classify.SaxsClassifier(model_file_path)
#    sxc.citrination_setup(address,api_key_file)
#    for data_type in ['precursors','spheres','peaks']:
#        data_path = os.path.join(os.getcwd(),'tests','test_data','solution_saxs',data_type)
#        data_files = glob.glob(os.path.join(data_path,'*.csv'))
#        for fpath in data_files:
#            print('testing classifier on {}'.format(fpath))
#            q_I = np.loadtxt(fpath,delimiter=',')
#            prof = saxs_math.profile_spectrum(q_I)
#            pops = sxc.citrination_predict(prof)
#            for popk,pop in pops.items():
#                print('\t{} populations: {} ({} certainty)'.format(popk,pop[0],pop[1]))
#
