import os
import itertools
from collections import OrderedDict

import yaml
import numpy as np

from . import get_regression_models, get_classification_models
from . import training_summary_yml
from .. import definitions as xrsdefs
from ..tools import primitives
from .regressor import Regressor
from .classifier import Classifier

def train_from_dataframe(data, output_dir, train_hyperparameters=False, select_features=False, save_models=False, model_types= {}):
    old_summary = {}
    if os.path.isfile(training_summary_yml): 
        with open(training_summary_yml,'rb') as yml_file:
            old_summary = yaml.load(yml_file)
    # classification models: 
    cls_models = train_classification_models(data, train_hyperparameters, select_features)
    # regression models:
    reg_models = train_regression_models(data, train_hyperparameters, select_features)
    # optionally, save the models:
    # this adds/updates yml files and also adds the models
    # to the regression_models and classification_models dicts.
    if save_models:
        cl_dir = os.path.join(output_dir,'classifiers')
        if not os.path.exists(cl_dir): os.mkdir(cl_dir)
        reg_dir = os.path.join(output_dir,'regressors')
        if not os.path.exists(reg_dir): os.mkdir(reg_dir)
        summary_reg = save_regression_models(reg_dir, reg_models)
        summary_cl = save_classification_models(cl_dir, cls_models)
        summary = collect_summary(old_summary, summary_reg, summary_cl)
        yml_f = os.path.join(output_dir,'training_summary.yml')
        with open(yml_f,'w') as yml_file:
            yaml.dump(summary,yml_file)

def train_classification_models(data,train_hyperparameters=False,select_features=False):
    """Train all classifiers that are trainable from `data`.

    Parameters
    ----------
    data : pandas.DataFrame
        dataframe containing features and labels
    train_hyperparameters : bool
        if True, cross-validation metrics are used to select model hyperparameters 

    Returns
    -------
    cls_models : dict
        Embedded dicts containing all possible classification models
        trained on the given dataset `data`.
    """
    # get a reference to the currently-loaded classification models dict
    classification_models = get_classification_models()
    
    new_cls_models = {}
    new_cls_models['main_classifiers'] = {}

    # find all existing types of populations in training data:
    all_sys_cls = data['system_class'].tolist()

    data_copy = data.copy()
    for struct_nm in xrsdefs.structure_names:
        print('Training binary classifier for '+struct_nm+' structures')
        model_id = struct_nm+'_binary'
        #
        # binary classifier model type is specified here!
        # we __should__ be able to try various models just by changing this.
        #
        new_model_type ='knn'
        #new_model_type ='d_tree'
        #new_model_type ='linear_svm_hinge'
        #new_model_type ='random_forest'
        #new_model_type = 'linear_svm'
        #new_model_type = 'non_linear_svm'
        #new_model_type = 'sgd_classifier'
        #new_model_type = 'logistic_regressor'
        model = Classifier(new_model_type, model_id)
        labels = [struct_nm in sys_cls for sys_cls in all_sys_cls]
        data_copy.loc[:,model_id] = labels
        if ('main_classifiers' in classification_models) \
        and (model_id in classification_models['main_classifiers']) \
        and (classification_models['main_classifiers'][model_id].trained) \
        and (classification_models['main_classifiers'][model_id].model_type == new_model_type):
            old_pars = classification_models['main_classifiers'][model_id].model.get_params()
            for param_nm in model.models_and_params[new_model_type]:
                model.model.set_params(**{param_nm:old_pars[param_nm]})
        # binary classifiers should be trained to avoid false positives:
        # use 'precision' as the scoring function
        model.train(data_copy, 'precision', train_hyperparameters, select_features)
        if model.trained:
            f1_score = model.cross_valid_results['f1_macro']
            acc = model.cross_valid_results['accuracy']
            prec = model.cross_valid_results['precision']
            rec = model.cross_valid_results['recall']
            print('--> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
        else:
            print('--> {} untrainable- default value: {}'.format(model_id,model.default_val))
        new_cls_models['main_classifiers'][model_id] = model

    # There are 2**n possible outcomes for n binary classifiers.
    # For the (2**n)-1 non-null outcomes, a second classifier is used,
    # to count the number of populations of each structural type.

    all_flag_combs = itertools.product([True,False],repeat=len(xrsdefs.structure_names))
    for flags in all_flag_combs:
        if sum(flags) > 0:
            flag_idx = np.ones(data.shape[0],dtype=bool)
            model_id = ''
            for struct_nm, flag in zip(xrsdefs.structure_names,flags):
                struct_flag_idx = np.array([(struct_nm in sys_cls) == flag for sys_cls in all_sys_cls])
                flag_idx = flag_idx & struct_flag_idx
                if flag:
                    if model_id: model_id += '__'
                    model_id += struct_nm
            print('Training system classifier for '+model_id)
            # get all samples whose system_class matches the flags
            flag_data = data.loc[flag_idx,:].copy()
            if flag_data.shape[0] > 0: # we have the data with this system class in the training set
                # train the classifier
                #new_model_type = 'logistic_regressor'
                #new_model_type = 'sgd_classifier'
                #new_model_type = 'non_linear_svm'
                #new_model_type = 'linear_svm'
                #new_model_type ='random_forest'
                #new_model_type ='linear_svm_hinge'
                #new_model_type ='d_tree'
                new_model_type ='knn'
                if model_id == "diffuse__disordered":
                    new_model_type = 'linear_svm'

                model = Classifier(new_model_type, 'system_class')
                if ('main_classifiers' in classification_models) \
                and (model_id in classification_models['main_classifiers']) \
                and (classification_models['main_classifiers'][model_id].trained) \
                and (classification_models['main_classifiers'][model_id].model_type == new_model_type):
                    old_pars = classification_models['main_classifiers'][model_id].model.get_params()
                    for param_nm in model.models_and_params[new_model_type]:
                        model.model.set_params(**{param_nm:old_pars[param_nm]})
                # system classifiers should use f1_macro or accuracy
                model.train(flag_data, 'accuracy', train_hyperparameters, select_features)
                if model.trained:
                    f1_score = model.cross_valid_results['f1_macro']
                    acc = model.cross_valid_results['accuracy']
                    prec = model.cross_valid_results['precision']
                    rec = model.cross_valid_results['recall']
                    print('--> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
                else:
                    print('--> {} untrainable- default value: {}'.format(model_id,model.default_val))
                # save the classifier
                new_cls_models['main_classifiers'][model_id] = model

    sys_cls_labels = list(data['system_class'].unique())
    # 'unidentified' systems will have no sub-classifiers; drop this label up front 
    if 'unidentified' in sys_cls_labels: sys_cls_labels.remove('unidentified')

    for sys_cls in sys_cls_labels:
        print('Training classifiers for system class {}'.format(sys_cls))
        new_cls_models[sys_cls] = {}
        sys_cls_data = data.loc[data['system_class']==sys_cls].copy()
        # drop the columns where all values are None:
        #sys_cls_data.dropna(axis=1,how='all',inplace=True)

        # every system class must have a noise classifier
        print('    Training noise classifier for system class {}'.format(sys_cls))
        new_model_type = 'logistic_regressor'
        #new_model_type = 'non_linear_svm'
        #new_model_type = 'linear_svm'
        #new_model_type ='random_forest'
        #new_model_type ='linear_svm_hinge'
        #new_model_type ='d_tree'
        #new_model_type ='knn'

        model = Classifier(new_model_type, 'noise_model')
        if (sys_cls in classification_models) \
        and ('noise_model' in classification_models[sys_cls]) \
        and (classification_models[sys_cls]['noise_model'].trained) \
        and (classification_models[sys_cls]['noise_model'].model_type == new_model_type):
            old_pars = classification_models[sys_cls]['noise_model'].model.get_params()
            for param_nm in model.models_and_params[new_model_type]:
                model.model.set_params(**{param_nm:old_pars[param_nm]})
        model.train(sys_cls_data, 'accuracy', train_hyperparameters, select_features)
        if model.trained:
            f1_score = model.cross_valid_results['f1_macro']
            acc = model.cross_valid_results['accuracy']
            prec = model.cross_valid_results['precision']
            rec = model.cross_valid_results['recall']
            print('    --> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
        else: 
            print('    --> {} untrainable- default value: {}'.format('noise_model',model.default_val))
        new_cls_models[sys_cls]['noise_model'] = model

        # each population has some classifiers for form factor and settings
        for ipop, struct in enumerate(sys_cls.split('__')):
            pop_id = 'pop{}'.format(ipop)
            new_cls_models[sys_cls][pop_id] = {}
            print('    Training classifiers for population {}'.format(pop_id))

            # every population must have a form classifier
            form_header = pop_id+'_form'
            print('    Training: {}'.format(form_header))
            #new_model_type = 'logistic_regressor'
            #new_model_type = 'non_linear_svm'
            #new_model_type = 'linear_svm'
            #new_model_type ='random_forest'
            new_model_type ='linear_svm_hinge'
            #new_model_type ='d_tree'
            #new_model_type ='knn'
            #new_model_type ='knn'
            model = Classifier(new_model_type, form_header)
            if (sys_cls in classification_models) \
            and (pop_id in classification_models[sys_cls]) \
            and ('form' in classification_models[sys_cls][pop_id]) \
            and (classification_models[sys_cls][pop_id]['form'].trained) \
            and (classification_models[sys_cls][pop_id]['form'].model_type == new_model_type):
                old_pars = classification_models[sys_cls][pop_id]['form'].model.get_params()
                for param_nm in model.models_and_params[new_model_type]:
                    model.model.set_params(**{param_nm:old_pars[param_nm]})
            model.train(sys_cls_data, 'accuracy', train_hyperparameters, select_features)
            if model.trained:
                f1_score = model.cross_valid_results['f1_macro']
                acc = model.cross_valid_results['accuracy']
                prec = model.cross_valid_results['precision']
                rec = model.cross_valid_results['recall']
                print('    --> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
            else: 
                print('    --> {} untrainable- default value: {}'.format(form_header,model.default_val))
            new_cls_models[sys_cls][pop_id]['form'] = model

            # add classifiers for any model-able structure settings 
            for stg_nm in xrsdefs.modelable_structure_settings[struct]:
                stg_header = pop_id+'_'+stg_nm
                print('    Training: {}'.format(stg_header))
                new_model_type = 'logistic_regressor'
                model = Classifier(new_model_type, stg_header)
                if (sys_cls in classification_models) \
                and (pop_id in classification_models[sys_cls]) \
                and (stg_nm in classification_models[sys_cls][pop_id]) \
                and (classification_models[sys_cls][pop_id][stg_nm].trained) \
                and (classification_models[sys_cls][pop_id][stg_nm].model_type == new_model_type):
                    old_pars = classification_models[sys_cls][pop_id][stg_nm].model.get_params()
                    for param_nm in model.models_and_params[new_model_type]:
                        model.model.set_params(**{param_nm:old_pars[param_nm]})
                model.train(sys_cls_data, 'accuracy', train_hyperparameters, select_features)
                if model.trained:
                    f1_score = model.cross_valid_results['f1_macro']
                    acc = model.cross_valid_results['accuracy']
                    prec = model.cross_valid_results['precision']
                    rec = model.cross_valid_results['recall']
                    print('    --> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
                else: 
                    print('    --> {} untrainable- default value: {}'.format(stg_header,model.default_val))
                new_cls_models[sys_cls][pop_id][stg_nm] = model

            # add classifiers for any model-able form factor settings
            all_ff_labels = list(sys_cls_data[form_header].unique())
            for ff in all_ff_labels:
                form_data = sys_cls_data.loc[sys_cls_data[form_header]==ff].copy()
                new_cls_models[sys_cls][pop_id][ff] = {}
                print('    Training classifiers for {} with {} form factors'.format(pop_id,ff))
                for stg_nm in xrsdefs.modelable_form_factor_settings[ff]:
                    stg_header = pop_id+'_'+stg_nm
                    print('        Training: {}'.format(stg_header))
                    new_model_type = 'logistic_regressor'
                    model = Classifier(new_model_type, stg_header)
                    if (sys_cls in classification_models) \
                    and (pop_id in classification_models[sys_cls]) \
                    and (ff in classification_models[sys_cls][pop_id]) \
                    and (stg_nm in classification_models[sys_cls][pop_id][ff]) \
                    and (classification_models[sys_cls][pop_id][ff][stg_nm].trained) \
                    and (classification_models[sys_cls][pop_id][ff][stg_nm].model_type == new_model_type):
                        old_pars = classification_models[sys_cls][pop_id][ff][stg_nm].model.get_params()
                        for param_nm in model.models_and_params[new_model_type]:
                            model.model.set_params(**{param_nm:old_pars[param_nm]})
                    model.train(form_data, 'accuracy', train_hyperparameters, select_features)
                    if model.trained:
                        f1_score = model.cross_valid_results['f1_macro']
                        acc = model.cross_valid_results['accuracy']
                        prec = model.cross_valid_results['precision']
                        rec = model.cross_valid_results['recall']
                        print('        --> f1_macro: {}, accuracy: {}, precision: {}, recall: {}'.format(f1_score,acc,prec,rec))
                    else: 
                        print('        --> {} untrainable- default value: {}'.format(stg_header,model.default_val))
                    new_cls_models[sys_cls][pop_id][ff][stg_nm] = model

    return new_cls_models


def save_classification_models(output_dir, models):
    """Serialize `models` to .yml files, and also save them as module attributes.

    The models and scalers are saved to .yml,
    and a report of the cross-validation is saved to .txt.
    xrsdkit.models.classification_models is updated with all `models`.

    Parameters
    ----------
    models : dict
        embedded dict of models, similar to output of train_regression_models().
    """
    cl_root_dir = output_dir
    # get a reference to the currently-loaded classification models dict
    model_dict = get_classification_models()
    summary = {}
    if not os.path.exists(cl_root_dir): os.mkdir(cl_root_dir)

    if 'main_classifiers' in models:
        model_dict['main_classifiers'] = models['main_classifiers']
        if not os.path.exists(os.path.join(cl_root_dir,'main_classifiers')):
            os.mkdir(os.path.join(cl_root_dir,'main_classifiers'))
        for model_name, mod in model_dict['main_classifiers'].items():
            yml_path = os.path.join(cl_root_dir,'main_classifiers', model_name + '.yml')
            txt_path = os.path.join(cl_root_dir,'main_classifiers', model_name + '.txt')
            pickle_path = os.path.join(cl_root_dir,'main_classifiers', model_name + '.pickle')
            mod.save_model_data(yml_path,txt_path, pickle_path)
            summary[model_name] = primitives(mod.get_cv_summary())

    all_sys_cls = list(models.keys())
    all_sys_cls.remove('main_classifiers')
    for sys_cls in all_sys_cls: 
        sys_cls_dir = os.path.join(cl_root_dir,sys_cls)
        if not sys_cls in model_dict: model_dict[sys_cls] = {}
        if not os.path.exists(sys_cls_dir): os.mkdir(sys_cls_dir)
        if 'noise_model' in models[sys_cls]:
            model_dict[sys_cls]['noise_model'] = models[sys_cls]['noise_model']
            yml_path = os.path.join(sys_cls_dir,'noise_model.yml')
            txt_path = os.path.join(sys_cls_dir,'noise_model.txt')
            pickle_path = os.path.join(sys_cls_dir, 'noise_model.pickle')
            models[sys_cls]['noise_model'].save_model_data(yml_path,txt_path, pickle_path)
            model_name = sys_cls + '_noise_model'
            summary[model_name] = primitives(models[sys_cls]['noise_model'].get_cv_summary())

        for ipop,struct in enumerate(sys_cls.split('__')):
            pop_id = 'pop{}'.format(ipop)
            pop_dir = os.path.join(sys_cls_dir,pop_id)
            if not os.path.exists(pop_dir): os.mkdir(pop_dir)
            if not pop_id in model_dict[sys_cls]: model_dict[sys_cls][pop_id] = {}

            if 'form' in models[sys_cls][pop_id]:
                model_dict[sys_cls][pop_id]['form'] = models[sys_cls][pop_id]['form']
                yml_path = os.path.join(pop_dir,'form.yml')
                txt_path = os.path.join(pop_dir,'form.txt')
                pickle_path = os.path.join(pop_dir, 'form.pickle')
                models[sys_cls][pop_id]['form'].save_model_data(yml_path,txt_path, pickle_path)
                model_name = sys_cls + '_' + pop_id +'_form'
                summary[model_name] = primitives(models[sys_cls][pop_id]['form'].get_cv_summary())
               
            for stg_nm in xrsdefs.modelable_structure_settings[struct]:
                if stg_nm in models[sys_cls][pop_id]:
                    model_dict[sys_cls][pop_id][stg_nm] = models[sys_cls][pop_id][stg_nm]
                    yml_path = os.path.join(pop_dir,stg_nm+'.yml')
                    txt_path = os.path.join(pop_dir,stg_nm+'.txt')
                    pickle_path = os.path.join(pop_dir,stg_nm+ '.pickle')
                    models[sys_cls][pop_id][stg_nm].save_model_data(yml_path,txt_path, pickle_path)
                    model_name = sys_cls + '_' + pop_id + '_' + stg_nm
                    summary[model_name] = primitives(models[sys_cls][pop_id][stg_nm].get_cv_summary())

            for ff_id in xrsdefs.form_factor_names:
                if ff_id in models[sys_cls][pop_id]:
                    form_dir = os.path.join(pop_dir,ff_id)
                    if not os.path.exists(form_dir): os.mkdir(form_dir)
                    model_dict[sys_cls][pop_id][ff_id] = {}
                    for stg_nm in xrsdefs.modelable_form_factor_settings[ff_id]:
                        model_dict[sys_cls][pop_id][ff_id][stg_nm] = models[sys_cls][pop_id][ff_id][stg_nm]
                        yml_path = os.path.join(form_dir,stg_nm+'.yml')
                        txt_path = os.path.join(form_dir,stg_nm+'.txt')
                        pickle_path = os.path.join(form_dir,stg_nm+'.pickle')
                        models[sys_cls][pop_id][ff_id][stg_nm].save_model_data(yml_path,txt_path, pickle_path)
                        model_name = sys_cls + '_' + pop_id + '_' + ff_id + '_' + stg_nm
                        summary[model_name] = primitives(models[sys_cls][pop_id][ff_id][stg_nm].get_cv_summary())
    return summary


def train_regression_models(data,train_hyperparameters=False,select_features=False):
    """Train all regression models trainable from `data`. 

    Parameters
    ----------
    data : pandas.DataFrame
        dataframe containing features and labels
    train_hyperparameters : bool
        if True, the models will be optimized
        over a grid of hyperparameters during training

    Returns
    -------
    reg_models : dict
        embedded dictionary with blank spaces for all trainable regression models 
    """
    # get a reference to the currently-loaded regression models dict
    regression_models = get_regression_models()
    new_reg_models = {} 
    sys_cls_labels = list(data['system_class'].unique())
    # 'unidentified' systems will have no regression models:
    if 'unidentified' in sys_cls_labels: sys_cls_labels.pop(sys_cls_labels.index('unidentified'))
    for sys_cls in sys_cls_labels:
        print('training regressors for system class {}'.format(sys_cls))
        new_reg_models[sys_cls] = {}
        sys_cls_data = data.loc[data['system_class']==sys_cls].copy()
        # drop the columns where all values are None:
        #sys_cls_data.dropna(axis=1,how='all',inplace=True)

        # every system class has regressors for one or more noise models 
        new_reg_models[sys_cls]['noise'] = {}
        all_noise_models = list(sys_cls_data['noise_model'].unique())
        for modnm in all_noise_models:
            print('    training regressors for noise model {}'.format(modnm))
            new_reg_models[sys_cls]['noise'][modnm] = {}
            noise_model_data = sys_cls_data.loc[sys_cls_data['noise_model']==modnm].copy()
            for pnm in list(xrsdefs.noise_params[modnm].keys())+['I0_fraction']:
                if not pnm == 'I0':
                    param_header = 'noise_'+pnm
                    new_model_type = 'ridge_regressor'
                    model = Regressor(new_model_type, param_header)
                    print('        training {}'.format(param_header))
                    if (sys_cls in regression_models) \
                    and ('noise' in regression_models[sys_cls]) \
                    and (modnm in regression_models[sys_cls]['noise']) \
                    and (pnm in regression_models[sys_cls]['noise'][modnm]) \
                    and (regression_models[sys_cls]['noise'][modnm][pnm].trained) \
                    and (regression_models[sys_cls]['noise'][modnm][pnm].model_type == new_model_type): 
                        old_pars = regression_models[sys_cls]['noise'][modnm][pnm].model.get_params()
                        for param_nm in model.models_and_params[new_model_type]:
                            model.model.set_params(**{param_nm:old_pars[param_nm]})
                    model.train(noise_model_data, 'neg_mean_absolute_error', train_hyperparameters, select_features)
                    if model.trained:
                        grpsz_wtd_mean_MAE = model.cross_valid_results['groupsize_weighted_average_MAE']
                        print('        --> weighted-average MAE: {}'.format(grpsz_wtd_mean_MAE))
                    else: 
                        print('        --> {} untrainable- default result: {}'.format(param_header,model.default_val))
                    new_reg_models[sys_cls]['noise'][modnm][pnm] = model 

        # use the sys_cls to identify the populations and their structures
        for ipop,struct in enumerate(sys_cls.split('__')):
            pop_id = 'pop{}'.format(ipop)
            new_reg_models[sys_cls][pop_id] = {}
            # every population must have a model for I0_fraction
            param_header = pop_id+'_I0_fraction'
            new_model_type = 'ridge_regressor'
            model = Regressor(new_model_type, param_header)
            print('    training regressors for population {}'.format(pop_id))
            print('        training {}'.format(param_header))
            if (sys_cls in regression_models) \
            and (pop_id in regression_models[sys_cls]) \
            and ('I0_fraction' in regression_models[sys_cls][pop_id]) \
            and (regression_models[sys_cls][pop_id]['I0_fraction'].trained) \
            and (regression_models[sys_cls][pop_id]['I0_fraction'].model_type == new_model_type): 
                old_pars = regression_models[sys_cls][pop_id]['I0_fraction'].model.get_params()
                for param_nm in model.models_and_params[new_model_type]:
                    model.model.set_params(**{param_nm:old_pars[param_nm]})
            model.train(sys_cls_data, 'neg_mean_absolute_error', train_hyperparameters, select_features)
            if model.trained:
                grpsz_wtd_mean_MAE = model.cross_valid_results['groupsize_weighted_average_MAE']
                print('        --> weighted-average MAE: {}'.format(grpsz_wtd_mean_MAE))
            else: 
                print('        --> {} untrainable- default result: {}'.format(param_header,model.default_val))
            new_reg_models[sys_cls][pop_id]['I0_fraction'] = model 
                
            # add regressors for any modelable structure params 
            for stg_nm in xrsdefs.modelable_structure_settings[struct]:
                stg_header = pop_id+'_'+stg_nm
                new_reg_models[sys_cls][pop_id][stg_nm] = {}
                stg_labels = list(sys_cls_data[stg_header].unique())
                for stg_label in stg_labels:
                    new_reg_models[sys_cls][pop_id][stg_nm][stg_label] = {}
                    stg_label_data = sys_cls_data.loc[sys_cls_data[stg_header]==stg_label].copy()
                    print('    training regressors for {} with {}=={}'.format(pop_id,stg_nm,stg_label))
                    for pnm in xrsdefs.structure_params(struct,{stg_nm:stg_label}):
                        param_header = pop_id+'_'+pnm
                        new_model_type = 'ridge_regressor'
                        model = Regressor(new_model_type, param_header)
                        print('        training {}'.format(param_header))
                        if (sys_cls in regression_models) \
                        and (pop_id in regression_models[sys_cls]) \
                        and (stg_nm in regression_models[sys_cls][pop_id]) \
                        and (stg_label in regression_models[sys_cls][pop_id][stg_nm]) \
                        and (pnm in regression_models[sys_cls][pop_id][stg_nm][stg_label]) \
                        and (regression_models[sys_cls][pop_id][stg_nm][stg_label][pnm].trained) \
                        and (regression_models[sys_cls][pop_id][stg_nm][stg_label][pnm].model_type == new_model_type):
                            old_pars = regression_models[sys_cls][pop_id][stg_nm][stg_label][pnm].model.get_params()
                            for param_nm in model.models_and_params[new_model_type]:
                                model.model.set_params(**{param_nm:old_pars[param_nm]})
                        model.train(stg_label_data, 'neg_mean_absolute_error', train_hyperparameters, select_features)
                        if model.trained:
                            grpsz_wtd_mean_MAE = model.cross_valid_results['groupsize_weighted_average_MAE']
                            print('        --> weighted-average MAE: {}'.format(grpsz_wtd_mean_MAE))
                        else: 
                            print('        --> {} untrainable- default result: {}'.format(param_header,model.default_val))
                        new_reg_models[sys_cls][pop_id][stg_nm][stg_label][pnm] = model 

            # get all unique form factors for this population
            form_header = pop_id+'_form'
            form_specifiers = list(sys_cls_data[form_header].unique())

            # for each form, make additional regression models
            for form_id in form_specifiers:
                form_data = sys_cls_data.loc[data[form_header]==form_id].copy()
                new_reg_models[sys_cls][pop_id][form_id] = {}
                print('    training regressors for {} with {} form factors'.format(pop_id,form_id))
                for pnm in xrsdefs.form_factor_params[form_id]:
                    param_header = pop_id+'_'+pnm
                    new_model_type = 'ridge_regressor'
                    model = Regressor(new_model_type, param_header)
                    print('        training {}'.format(param_header))
                    if (sys_cls in regression_models) \
                    and (pop_id in regression_models[sys_cls]) \
                    and (form_id in regression_models[sys_cls][pop_id]) \
                    and (pnm in regression_models[sys_cls][pop_id][form_id]) \
                    and (regression_models[sys_cls][pop_id][form_id][pnm].trained) \
                    and (regression_models[sys_cls][pop_id][form_id][pnm].model_type == new_model_type):
                        old_pars = regression_models[sys_cls][pop_id][form_id][pnm].model.get_params()
                        for param_nm in model.models_and_params[new_model_type]:
                            model.model.set_params(**{param_nm:old_pars[param_nm]})
                    model.train(form_data, 'neg_mean_absolute_error', train_hyperparameters, select_features)
                    if model.trained:
                        grpsz_wtd_mean_MAE = model.cross_valid_results['groupsize_weighted_average_MAE']
                        print('        --> weighted-average MAE: {}'.format(grpsz_wtd_mean_MAE))
                    else: 
                        print('        --> {} untrainable- default result: {}'.format(param_header,model.default_val))
                    new_reg_models[sys_cls][pop_id][form_id][pnm] = model 

                # add regressors for any modelable form factor params 
                for stg_nm in xrsdefs.modelable_form_factor_settings[form_id]:
                    stg_header = pop_id+'_'+stg_nm
                    stg_labels = list(form_data[stg_header].unique())
                    new_reg_models[sys_cls][pop_id][form_id][stg_nm] = {}
                    for stg_label in stg_labels:
                        new_reg_models[sys_cls][pop_id][form_id][stg_nm][stg_label] = {}
                        stg_label_data = form_data.loc[form_data[stg_header]==stg_label].copy()
                        print('    training regressors for {} with {} form factors with {}=={}'.format(pop_id,form_id,stg_nm,stg_label))
                        for pnm in xrsdefs.additional_form_factor_params(form_id,{stg_nm:stg_label}):
                            param_header = pop_id+'_'+pnm
                            new_model_type = 'ridge_regressor'
                            model = Regressor(new_model_type, param_header)
                            print('        training {}'.format(param_header))
                            if (sys_cls in regression_models) \
                            and (pop_id in regression_models[sys_cls]) \
                            and (form_id in regression_models[sys_cls][pop_id]) \
                            and (stg_nm in regression_models[sys_cls][pop_id][form_id]) \
                            and (stg_label in regression_models[sys_cls][pop_id][form_id][stg_nm]) \
                            and (pnm in regression_models[sys_cls][pop_id][form_id][stg_nm][stg_label]) \
                            and (regression_models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm].trained) \
                            and (regression_models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm].model_type == new_model_type):
                                old_pars = regression_models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm].model.get_params()
                                for param_nm in model.models_and_params[new_model_type]:
                                    model.model.set_params(**{param_nm:old_pars[param_nm]})
                            model.train(stg_label_data, 'neg_mean_absolute_error', train_hyperparameters, select_features)
                            if model.trained:
                                grpsz_wtd_mean_MAE = model.cross_valid_results['groupsize_weighted_average_MAE']
                                print('        --> weighted-average MAE: {}'.format(grpsz_wtd_mean_MAE))
                            else: 
                                print('        --> {} untrainable- default result: {}'.format(param_header,model.default_val))
                            new_reg_models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm] = model 

    return new_reg_models


def save_regression_models(output_dir, models):
    """Serialize `models` to .yml files, and also save them as module attributes.

    The models and scalers are saved to .yml,
    and a report of the cross-validation is saved to .txt.
    xrsdkit.models.regression_models is updated with all `models`.

    Parameters
    ----------
    models : dict
        embedded dict of models, similar to output of train_regression_models().
    """
    rg_root_dir = output_dir
    # get a reference to the currently-loaded regression models dict
    model_dict = get_regression_models()
    summary = {}
    if not os.path.exists(rg_root_dir): os.mkdir(rg_root_dir)
    for sys_cls in models.keys():
        sys_cls_dir = os.path.join(rg_root_dir,sys_cls)
        if not os.path.exists(sys_cls_dir): os.mkdir(sys_cls_dir)
        if not sys_cls in model_dict: model_dict[sys_cls] = {}
        if 'noise' in models[sys_cls]:
            noise_dir = os.path.join(sys_cls_dir,'noise')
            if not os.path.exists(noise_dir): os.mkdir(noise_dir)
            if not 'noise' in model_dict[sys_cls]: model_dict[sys_cls]['noise'] = {}
            for modnm in models[sys_cls]['noise'].keys():
                noise_model_dir = os.path.join(noise_dir,modnm)
                if not os.path.exists(noise_model_dir): os.mkdir(noise_model_dir)
                if not modnm in model_dict[sys_cls]['noise']: model_dict[sys_cls]['noise'][modnm] = {}
                for pnm, model in models[sys_cls]['noise'][modnm].items():
                    model_dict[sys_cls]['noise'][modnm][pnm] = model 
                    yml_path = os.path.join(noise_model_dir,pnm+'.yml')
                    txt_path = os.path.join(noise_model_dir,pnm+'.txt')
                    pickle_path = os.path.join(noise_model_dir,pnm+'.pickle')
                    models[sys_cls]['noise'][modnm][pnm].save_model_data(yml_path,txt_path, pickle_path)
                    model_name = sys_cls + '_noise_' + modnm + "_" + pnm
                    summary[model_name] = primitives(models[sys_cls]['noise'][modnm][pnm].get_cv_summary())

        for ipop,struct in enumerate(sys_cls.split('__')):
            pop_id = 'pop{}'.format(ipop)
            pop_dir = os.path.join(sys_cls_dir,pop_id)
            if not os.path.exists(pop_dir): os.mkdir(pop_dir)
            if not pop_id in model_dict[sys_cls]: model_dict[sys_cls][pop_id] = {}
            
            if 'I0_fraction' in models[sys_cls][pop_id]:
                model_dict[sys_cls][pop_id]['I0_fraction'] = models[sys_cls][pop_id]['I0_fraction']
                yml_path = os.path.join(pop_dir,'I0_fraction.yml')
                txt_path = os.path.join(pop_dir,'I0_fraction.txt')
                pickle_path = os.path.join(pop_dir,'I0_fraction.pickle')
                models[sys_cls][pop_id]['I0_fraction'].save_model_data(yml_path,txt_path, pickle_path)
                model_name = sys_cls + "_" + pop_id + '_I0_fraction'
                summary[model_name] = primitives(models[sys_cls][pop_id]['I0_fraction'].get_cv_summary())
               
            for stg_nm in xrsdefs.modelable_structure_settings[struct]:
                if stg_nm in models[sys_cls][pop_id]:
                    stg_dir = os.path.join(pop_dir,stg_nm)
                    if not os.path.exists(stg_dir): os.mkdir(stg_dir)
                    if not stg_nm in model_dict[sys_cls][pop_id]: model_dict[sys_cls][pop_id][stg_nm] = {}
                    for stg_label in models[sys_cls][pop_id][stg_nm].keys():
                        stg_label_dir = os.path.join(stg_dir,stg_label)
                        if not os.path.exists(stg_label_dir): os.mkdir(stg_label_dir)
                        if not stg_label in model_dict[sys_cls][pop_id][stg_nm]: 
                            model_dict[sys_cls][pop_id][stg_nm][stg_label] = {}
                        for pnm in xrsdefs.structure_params(struct,{stg_nm:stg_label}):
                            if pnm in models[sys_cls][pop_id][stg_nm][stg_label]:
                                model_dict[sys_cls][pop_id][stg_nm][stg_label][pnm] = \
                                models[sys_cls][pop_id][stg_nm][stg_label][pnm]
                                yml_path = os.path.join(stg_label_dir,pnm+'.yml')
                                txt_path = os.path.join(stg_label_dir,pnm+'.txt')
                                pickle_path = os.path.join(stg_label_dir,pnm+'.pickle')
                                models[sys_cls][pop_id][stg_nm][stg_label][pnm].save_model_data(yml_path,txt_path, pickle_path)
                                model_name = sys_cls + "_" + pop_id + "_" + stg_nm + "_"+ stg_label + "_" + pnm
                                summary[model_name] = primitives(models[sys_cls][pop_id][stg_nm][stg_label][pnm].get_cv_summary())
            
            for form_id in xrsdefs.form_factor_names:
                if form_id in models[sys_cls][pop_id]:
                    form_dir = os.path.join(pop_dir,form_id)
                    if not os.path.exists(form_dir): os.mkdir(form_dir)
                    if not form_id in model_dict[sys_cls][pop_id]: model_dict[sys_cls][pop_id][form_id] = {}
                    for pnm in xrsdefs.form_factor_params[form_id]:
                        if pnm in models[sys_cls][pop_id][form_id]:
                            model_dict[sys_cls][pop_id][form_id][pnm] = models[sys_cls][pop_id][form_id][pnm]
                            yml_path = os.path.join(form_dir,pnm+'.yml')
                            txt_path = os.path.join(form_dir,pnm+'.txt')
                            pickle_path = os.path.join(form_dir,pnm+'.pickle')
                            models[sys_cls][pop_id][form_id][pnm].save_model_data(yml_path,txt_path, pickle_path)
                            model_name = sys_cls + "_" + pop_id + "_" + form_id + "_"+ pnm
                            summary[model_name] = primitives(models[sys_cls][pop_id][form_id][pnm].get_cv_summary())

                    for stg_nm in xrsdefs.modelable_form_factor_settings[form_id]:
                        if stg_nm in models[sys_cls][pop_id][form_id]:
                            stg_dir = os.path.join(form_dir,stg_nm)
                            if not os.path.exists(stg_dir): os.mkdir(stg_dir)
                            model_dict[sys_cls][pop_id][form_id][stg_nm] = {}
                            for stg_label in models[sys_cls][pop_id][form_id][stg_nm].keys():
                                stg_label_dir = os.path.join(stg_dir,stg_label)
                                if not os.path.exists(stg_label_dir): os.mkdir(stg_label_dir)
                                if not stg_label in model_dict[sys_cls][pop_id][form_id][stg_nm]:
                                    model_dict[sys_cls][pop_id][form_id][stg_nm][stg_label] = {}
                                for pnm in xrsdefs.additional_form_factor_params(form_id,{stg_nm:stg_label}):
                                    model_dict[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm] = \
                                    models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm]
                                    yml_path = os.path.join(stg_label_dir,pnm+'.yml')
                                    txt_path = os.path.join(stg_label_dir,pnm+'.txt')
                                    pickle_path = os.path.join(stg_label_dir,pnm+'.pickle')
                                    models[sys_cls][pop_id][form_id][stg_nm][stg_label][pnm].save_model_data(yml_path,txt_path, pickle_path)
                                    model_name = sys_cls + "_" + pop_id + "_" + form_id + "_"+ stg_nm + "_" + stg_label + "_" + pnm
                                    summary[model_name] = primitives(models[sys_cls][pop_id]\
                                        [form_id][stg_nm][stg_label][pnm].get_cv_summary())
    return summary


def collect_summary(old_summary, summary_reg, summary_cl):
    summary = OrderedDict.fromkeys(['DESCRIPTION','CLASSIFIERS','REGRESSORS'])
    summary['DESCRIPTION'] = 'Each metric is reported with two values: '\
        'The first value of each metric is the value of the metric, '\
        'and the second value is the delta relative to the currently loaded models'
    summary['REGRESSORS'] = {}
    for k, v in summary_reg.items():
        if v:
            summary['REGRESSORS'][k] = {}
            summary['REGRESSORS'][k]['model_type'] = v['model_type']
            summary['REGRESSORS'][k]['scores'] = {}
            for metric, value in v['scores'].items():
                try:
                    diff = value-old_summary['REGRESSORS'][k]['scores'][metric][0]
                except:
                    diff = None
                summary['REGRESSORS'][k]['scores'][metric] = [value, diff]
    summary['CLASSIFIERS'] = {}
    for k, v in summary_cl.items():
        if v:
            summary['CLASSIFIERS'][k] = {}
            summary['CLASSIFIERS'][k]['model_type'] = v['model_type']
            summary['CLASSIFIERS'][k]['scores'] = {}
            for key, value in v['scores'].items():
                try:
                    diff = value-old_summary['CLASSIFIERS'][k]['scores'][key][0]
                except:
                    diff = None

                summary['CLASSIFIERS'][k]['scores'][key] = [value, diff]
    return summary


