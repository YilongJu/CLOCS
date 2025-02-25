#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 16 23:40:29 2020

@author: Dani Kiyasseh
"""

# %%
import numpy as np
from prepare_miscellaneous import obtain_information, obtain_saved_weights_name, make_saving_directory_contrastive, \
    modify_dataset_order_for_multi_task_learning, obtain_load_path_dir, determine_classification_setting
from prepare_network import cnn_network_contrastive, second_cnn_network
from run_experiment import train_model

# %%

dataset_list = ['physionet', 'physionet2017', 'cardiology', 'ptb', 'fetal', 'physionet2016', 'physionet2020', 'chapman',
                'chapman_pvc']  # ,'cipa']
batch_size_list = [256, 256, 16, 64, 64, 256, 256, 256, 256]  # , 512]
lr_list = [1e-4, 1e-4, 1e-4, 5e-5, 1e-4, 1e-4, 1e-4, 1e-4, 1e-4]  # , 1e-4]
nleads = 12  # 12 | 4
if nleads == 12:
    leads_list = [None, None, None, 'i', 'Abdomen 1', 'i',
                  "['I', 'II', 'III', 'aVL', 'aVR', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']",
                  "['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']",
                  "['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']"]  # 'II' for one lead, ['II','V1',etc.] for more leads
elif nleads == 4:
    leads_list = [None, None, None, 'i', 'Abdomen 1', 'i', "['II', 'V2', 'aVL', 'aVR']", "['II', 'V2', 'aVL', 'aVR']",
                  "['II', 'V2', 'aVL', 'aVR']"]  # 'II' for one lead, ['II','V1',etc.] for more leads
class_pair = ['', '', '', '', '', '', '', 'All Terms', '']

data2bs_dict = dict(zip(dataset_list, batch_size_list))
data2lr_dict = dict(zip(dataset_list, lr_list))
data2leads_dict = dict(zip(dataset_list, leads_list))
data2classpair_dict = dict(zip(dataset_list, class_pair))

""" Not Used - Just for User to Know """
perturbation_options = ['Gaussian', 'FlipAlongY', 'FlipAlongX']
downstream_task_options = ['', 'contrastive_ms', 'contrastive_ml', 'contrastive_msml',
                           'obtain_representation_contrastive']  # load normal data, load patient data for CPPC, load patient data for CPPC
""" ------------ """

trials_to_load_dict = {
    'CMC':
        {'input_perturbed': True,  # default is perturbed - do not change
         'perturbation': ['Gaussian']},  # needs to be a list to allow for sequence of perturbations
    'SimCLR':
        {'input_perturbed': True,  # default is perturbed - do not change
         'perturbation': ['Gaussian']},
    'CMSC':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
    'CMLC':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
    'CMSMLC':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
    'Linear':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
    'Fine-Tuning':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
    'Random':
        {'input_perturbed': False,  # default is NO perturbation
         'perturbation': ['']},
}

trials_to_run_dict = {
    'CMC':
        {'downstream_task': 'contrastive_ss',
         'nencoders': 2,  # must be same as nviews as per paper by Isola
         'nviews': 2},  # determines number of perturbations to perform
    'SimCLR':
        {'downstream_task': 'contrastive_ss',
         'nencoders': 1,  # this can be changed independently of nviews
         'nviews': 2},  # default method only contains 2 views
    'CMSC':
        {'downstream_task': 'contrastive_ms',  # determines which dataset version to load
         'nencoders': 1,  # this can be changed independently of nviews
         'nviews': 2},  # changing this will require remaking dataset #nviews = nsegments
    'CMLC':
        {'downstream_task': 'contrastive_ml',  # determines which dataset version to load
         'nencoders': 1,  # this can be changed independently of nviews
         'nviews': nleads},  # changing this will require remaking dataset #nviews = nleads
    'CMSMLC':
        {'downstream_task': 'contrastive_msml',  # determines which dataset version to load
         'nencoders': 1,  # this can be changed independently of nviews
         'nviews': nleads},  # changing this will require remaking dataset #nviews = nleads * nsegments
    'Linear':
        {'downstream_task': 'contrastive_ss',  # load ordinary datasets
         'nencoders': 1,  # this will depend on original self-supervision method used e.g. CPPC, CMC, etc.
         'nviews': 1},  # changing this will require remaking dataset
    'Fine-Tuning':
        {'downstream_task': 'contrastive_ss',  # load ordinary datasets
         'nencoders': 1,  # this will depend on original self-supervision method used e.g. CPPC, CMC, etc.
         'nviews': 1},  # changing this will require remaking dataset
    'Random':
        {'downstream_task': 'contrastive_ss',  # load ordinary datasets
         'nencoders': 1,  # this will depend on original self-supervision method used e.g. CPPC, CMC, etc.
         'nviews': 1},  # changing this will require remaking dataset
}


# %%
def run_configurations(basepath_to_data, phases, trial_to_load_list, trial_to_run_list, embedding_dim_list,
                       downstream_dataset_list, second_dataset_list, labelled_fraction_list):
    """ Run All Experiments 
    Args:
        phases (list): list of phases for training        
        trial_to_load_list (list): list of trials to load #this is needed for fine-tuning later on
        trial_to_run_list (list): list of trials to run
        embedding_dim_list (list): size of embedding for representation
        downstream_dataset_list (list): list of datasets to perform experiments on
    """
    # basepath_to_data = '/mnt/SecondaryHDD'
    # phases = ['train', 'val', 'test']
    # trial_to_load_list = ['SimCLR', 'CMSC', 'CMLC', 'CMSMLC']
    # trial_to_run_list = ['SimCLR', 'CMSC', 'CMLC', 'CMSMLC'] current trial to run and perform training # Fine-Tuning | Same as trial_to_load
    # embedding_dim_list = [64, 128, 256, 512, 32, 320]
    # downstream_dataset_list = ['chapman' ,'physionet2020']
    # second_dataset_list = ['physionet2020', 'cardiology', 'physionet2017', 'chapman'], 'physionet2020'] only used for fine-tuning & linear trials #keep as list of empty strings if pretraining
    # labelled_fraction_list = [0.25, 0.50, 0.75, 1.00] for finetuning and linear evaluation

    for trial_to_load, trial_to_run in zip(trial_to_load_list, trial_to_run_list):
        for embedding_dim in embedding_dim_list:  # embedding dimension to use for pretraining
            for downstream_dataset in downstream_dataset_list:  # dataset used for pretraining
                for second_dataset in second_dataset_list:  # dataset used for evaluation down the line
                    for labelled_fraction in labelled_fraction_list:
                        # second_dataset = 'physionet2020'
                        # downstream_dataset = 'chapman'
                        # embedding_dim = 64
                        # trial_to_run = 'SimCLR'
                        # trial_to_load = 'SimCLR'
                        # labelled_fraction = 0.25
                        downstream_task, nencoders, nviews = trials_to_run_dict[trial_to_run].values()
                        # downstream_task = 'contrastive_ss'
                        # nencoders = 1
                        # nviews = 2
                        input_perturbed, perturbation = trials_to_load_dict[trial_to_load].values()
                        # input_perturbed = True
                        # perturbation = ['Gaussian']
                        saved_weights = obtain_saved_weights_name(trial_to_run, phases)
                        # saved_weights = 'pretrained_weight'

                        """ Information for save_path_dir """
                        # data2leads_dict = {'physionet': None,
                        #  'physionet2017': None,
                        #  'cardiology': None,
                        #  'ptb': 'i',
                        #  'fetal': 'Abdomen 1',
                        #  'physionet2016': 'i',
                        #  'physionet2020': "['I', 'II', 'III', 'aVL', 'aVR', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']",
                        #  'chapman': "['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']",
                        #  'chapman_pvc': "['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']"}
                        original_leads, original_batch_size, original_held_out_lr, original_class_pair, original_modalities, original_fraction = obtain_information(
                            trial_to_load, downstream_dataset, second_dataset, data2leads_dict, data2bs_dict,
                            data2lr_dict, data2classpair_dict)
                        # original_leads = "['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']"
                        """ Information for actual training --- trial_to_run == trial_to_load when pretraining so they are the same """
                        leads, batch_size, held_out_lr, class_pair, modalities, fraction = obtain_information(
                            trial_to_run, downstream_dataset, second_dataset, data2leads_dict, data2bs_dict,
                            data2lr_dict, data2classpair_dict)

                        max_epochs = 400  # hard stop for training
                        max_seed = 5
                        seeds = np.arange(max_seed)
                        for seed in seeds:
                            save_path_dir, seed = make_saving_directory_contrastive(phases, downstream_dataset, trial_to_load, trial_to_run, seed, max_seed, downstream_task, embedding_dim, original_leads, input_perturbed, perturbation)
                            # if save_path_dir == 'do not train':
                            #    continue

                            if trial_to_run in ['Linear', 'Fine-Tuning', 'Random']:
                                original_downstream_dataset, modalities, leads, class_pair, fraction = modify_dataset_order_for_multi_task_learning(
                                    second_dataset, modalities, leads, class_pair, fraction)
                            else:
                                original_downstream_dataset = downstream_dataset  # to avoid overwriting downstream_dataset which is needed for next iterations

                            load_path_dir, save_path_dir = obtain_load_path_dir(phases, save_path_dir, trial_to_run,
                                                                                second_dataset, labelled_fraction,
                                                                                leads, max_seed, downstream_task)
                            if save_path_dir in ['do not train', 'do not test']:
                                continue

                            classification = determine_classification_setting(second_dataset, trial_to_run)
                            # basepath_to_data = '/mnt/SecondaryHDD'
                            # cnn_network_contrastive is a pytorch Model
                            # second_cnn_network is a linear layer added on top of a frozen model
                            # classification = '4-way'
                            train_model(basepath_to_data, cnn_network_contrastive, second_cnn_network, classification,
                                        load_path_dir, save_path_dir, seed, batch_size, held_out_lr, fraction,
                                        modalities, leads, saved_weights, phases, original_downstream_dataset,
                                        downstream_task, class_pair, input_perturbed, perturbation,
                                        trial_to_load=trial_to_load, trial_to_run=trial_to_run, nencoders=nencoders,
                                        embedding_dim=embedding_dim, nviews=nviews, labelled_fraction=labelled_fraction,
                                        num_epochs=max_epochs)


# %%
basepath_to_data = '/mnt/SecondaryHDD'
phases = ['train', 'val']  # ['test'] #['train','val'] #['test']
trial_to_load_list = ['SimCLR', 'CMSC', 'CMLC', 'CMSMLC']  # for loading pretrained weights
trial_to_run_list = ['SimCLR', 'CMSC', 'CMLC',
                     'CMSMLC']  # ['Linear','Linear','Linear','Linear'] #['Fine-Tuning','Fine-Tuning','Fine-Tuning','Fine-Tuning'] #['Linear','Linear','Linear','Linear'] #['Fine-Tuning','Fine-Tuning','Fine-Tuning','Fine-Tuning'] #['Fine-Tuning','Fine-Tuning','Fine-Tuning','Fine-Tuning']  #['Linear','Linear','Linear','Linear']  #['Random']#,'Fine-Tuning','Fine-Tuning','Fine-Tuning']#['SimCLR','CMSC','CMLC','CMSMLC'] #current trial to run and perform training # Fine-Tuning | Same as trial_to_load
embedding_dim_list = [320, 256, 128, 64, 32]
downstream_dataset_list = ['chapman']  # ,'physionet2020'] #dataset for pretraininng # 'chapman' | 'physionet2020'
second_dataset_list = [
    '']  # physionet2020'] #['physionet2020','cardiology','physionet2017','chapman']#,'physionet2020'] #only used for fine-tuning & linear trials #keep as list of empty strings if pretraining
labelled_fraction_list = [
    1]  # 0.25,0.50,0.75,1.00] #proportion of labelled training data to train on # SHOULD BE 1 for pretraining #[0.25,0.50,0.75,1.00] for finetuning and linear evaluation

if __name__ == '__main__':
    run_configurations(basepath_to_data, phases, trial_to_load_list, trial_to_run_list, embedding_dim_list,
                       downstream_dataset_list, second_dataset_list, labelled_fraction_list)
