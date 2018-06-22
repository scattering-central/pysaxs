from collections import OrderedDict
import os
import pandas as pd
import numpy as np
from sklearn import preprocessing
from pypif import pif
from citrination_client import PifSystemReturningQuery, DatasetQuery, DataQuery, Filter

from ..tools import profiler
from ..tools import piftools


def get_data_from_Citrination(client, dataset_id_list):
    """Get data from Citrination and create a dataframe.

    Parameters
    ----------
    client : citrination_client.CitrinationClient
        A python Citrination client for fetching data
    dataset_id_list : list of int
        List of dataset ids (integers) for fetching SAXS records

    Returns
    -------
    df_work : pandas.DataFrame
        dataframe containing features and labels
        obtained through `client` from the Citrination datasets
        listed in `dataset_id_list`
    pifs : list
        list of pif objects. Each of them contains data about one sample.
    """
    data = []
    reg_labels = []
    all_reg_labels = set()

    pifs = get_pifs_from_Citrination(client,dataset_id_list)

    for i in range(len(pifs)):
        pp = pifs[i]
        expt_id,t_utc,q_I,temp,pp_feats, cl_model_outputs, reg_model_outputs = piftools.unpack_pif(pp)
        feats = OrderedDict.fromkeys(profiler.profile_keys)
        feats.update(pp_feats)
        
        data_row = [expt_id]+list(feats.values())+[cl_model_outputs]+[i] # i will be the local_id
        data.append(data_row)
        for k,v in reg_model_outputs.items():
            all_reg_labels.add(k)
        reg_labels.append(reg_model_outputs)

    reg_labels_list = list(all_reg_labels)
    reg_labels_list.sort()

    for i in range(len(reg_labels)):
        lb = OrderedDict.fromkeys(reg_labels_list)
        lb.update(reg_labels[i])
        data[i] = data[i] + list(lb.values())

    colnames = ['experiment_id']
    colnames.extend(profiler.profile_keys)
    colnames.extend(['system_class'])
    colnames.extend(['local_id'])
    colnames.extend(reg_labels_list)

    d = pd.DataFrame(data=data, columns=colnames)
    df_work = d.where((pd.notnull(d)), None) # replace all NaN by None

    return df_work, pifs

def get_pifs_from_Citrination(client, dataset_id_list):
    all_hits = []
    for dataset in dataset_id_list:
        query = PifSystemReturningQuery(
            from_index=0,
            size=100,
            query=DataQuery(
                dataset=DatasetQuery(
                    id=Filter(
                    equal=dataset))))

        current_result = client.search.pif_search(query)
        while current_result.hits!=[]:
            all_hits.extend(current_result.hits)
            n_current_hits = len(current_result.hits)
            #n_hits += n_current_hits
            query.from_index += n_current_hits 
            current_result = client.search.pif_search(query)

    pifs = [x.system for x in all_hits]
    return pifs


def sampl_data_on_Citrination(client, data_cl, dataset_id_list, save_sample=True):
    """Create a sample of data and ship it on Citrination.

    Parameters
    ----------
    client : citrination_client.CitrinationClient
        A python Citrination client for fetching data
    data_cl : citrination_client.data.client.DataClient
        A python Citrination client encapsulating data management behavior.
    dataset_id_list : list of int
        List of dataset ids (integers) for fetching SAXS records
    save_sample : bool
        if True, the sample of data will be save on Citrination

    Returns
    -------
    data_sample_not_transf : pandas.DataFrame
        dataframe containing subset of rows
        that was chosen using distance between the samples;
        the data was not transformed;
    new_datase_ids : list
        when save_sample is True, list of ids of new datasets where the sample was saved;
        when save_sample is False, it is an empty list.
    count : int
        number of training samples included in the data_sample
    """
    data, pifs = get_data_from_Citrination(client, dataset_id_list)

    #### create data_sample ########################
    data_sample = pd.DataFrame(columns=data.columns)
    all_exp = data.experiment_id.unique()

    features = []
    features.extend(profiler.profile_keys_1)

    scaler = preprocessing.StandardScaler()
    scaler.fit(data[features])

    transformed_data = pd.DataFrame(columns=data.columns, data= data[data.columns])
    transformed_data[features] = scaler.transform(data[features])

    for exp_id in all_exp:
        df = transformed_data[transformed_data['experiment_id']==exp_id]
        sample = make_sample_one_experiment(df, 1.0)
        data_sample = data_sample.append(sample)
    ################################################

    count = data_sample.shape[0]

    samples_to_save = data_sample.local_id.tolist()
    data_sample_not_transf = pd.DataFrame(columns=data.columns)
    for samp_id in samples_to_save:
        data_sample_not_transf=data_sample_not_transf.append(data.iloc[samp_id])

    new_datase_ids = []
    if save_sample:
        # sort sample of pifs by classes
        all_sys_classes = data_sample.system_class.unique()
        pifs_by_classes = {}
        for cl in all_sys_classes:
            pifs_by_classes[cl] = []

        for samp_id in samples_to_save:
            cl = data.iloc[samp_id].system_class
            pifs_by_classes[cl].append(pifs[samp_id])

        my_list = ','.join(map(str, dataset_id_list))
        p = os.path.abspath(__file__)
        d = os.path.dirname(os.path.dirname(os.path.dirname(p)))
        for k,v in pifs_by_classes.items():
            ds = data_cl.create_dataset(k, "Sample of data from datasets: "+ my_list)
            new_datase_ids.append(ds.id)

            pif_file = os.path.join(d, k+'.json')
            pif.dump(v, open(pif_file,'w'))
            client.data.upload(ds.id, pif_file)

    return data_sample_not_transf, new_datase_ids, count


def make_sample_one_experiment(data_fr, min_distance):
    """make a sample from ONE experiment.
    Parameters
    ----------
    data_fr : pandas.DataFrame
        dataframe containing the samples from one experiment.
    min_distance : float
        the minimal allowed distance between the samples.
    Returns
    -------
    sample : pandas.DataFrame
        dataframe containing subset of rows
        that was chosen using distance between the samples
    """
    groups_by_class = data_fr.groupby('system_class')
    sample = pd.DataFrame(columns=data_fr.columns)
    for name, group in groups_by_class:
        df = pd.DataFrame(columns=data_fr.columns)
        df = df.append(group.iloc[0])
        for i in range(1, group.shape[0]):
            add_row = True
            for j in range(0, df.shape[0]):
                s = sum((group.iloc[i][profiler.profile_keys_1] - group.iloc[j][profiler.profile_keys_1]).abs())
                if s < min_distance:
                    add_row = False
            if add_row:
                df = df.append(group.iloc[i])
        sample = sample.append(df)
    return sample
