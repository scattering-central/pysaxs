from collections import OrderedDict

import numpy as np
import pandas as pd
from sklearn import linear_model
from sklearn.decomposition import PCA
from sklearn.metrics import f1_score, confusion_matrix, accuracy_score, precision_score, recall_score
from sklearn import svm
from sklearn.ensemble import RandomForestClassifier
from sklearn import tree
from sklearn.neighbors import KNeighborsClassifier

from .xrsd_model import XRSDModel

class Classifier(XRSDModel):
    """Class for models that classify attributes of material systems."""

    def __init__(self, model_type, metric, label):
        super(Classifier,self).__init__(model_type, metric, label)
        self.models_and_params = dict(
            logistic_regressor = dict(
                C = np.logspace(-1,3,num=15,endpoint=True,base=10.)
                ),
            sgd_classifier = dict(
                alpha = np.logspace(-1,2,num=4,endpoint=True,base=10.),
                l1_ratio = np.linspace(0.,1.,num=5,endpoint=True) 
                ),
            non_linear_svm = dict(
               C = np.logspace(-1,3,num=15,endpoint=True,base=10.)
               ),
            linear_svm = dict(
               penalty = ['l1', 'l2'],
               C = np.logspace(-1,3,num=15,endpoint=True,base=10.)
               ),
            linear_svm_hinge = dict(
               C = np.logspace(-1,3,num=15,endpoint=True,base=10.)
               ),
            random_forest = dict(
               n_estimators = [1, 5, 10, 50]
               ),
            d_tree = dict(),
            knn = dict(
                n_neighbors = [1,3,5,7],
                weights = ['uniform', 'distance']
                )
            )


    def build_model(self,model_hyperparams={}):
        if self.model_type ==  'logistic_regressor':
            penalty='l2'
            if 'penalty' in model_hyperparams: penalty = model_hyperparams['penalty']
            C = 1.
            if 'C' in model_hyperparams: C = model_hyperparams['C']
            solver = 'lbfgs'
            if 'solver' in model_hyperparams: solver = model_hyperparams['solver']
            new_model = linear_model.LogisticRegression(penalty=penalty, C=C, 
                class_weight='balanced', solver=solver, max_iter=100000)
        elif self.model_type == 'sgd_classifier':
            new_model = self.build_sgd_model(model_hyperparams)
        elif self.model_type == 'non_linear_svm':
            C = 1.
            if 'C' in model_hyperparams: C = model_hyperparams['C']
            new_model = svm.SVC(C=C, kernel = 'poly', class_weight='balanced', probability=True, gamma='scale')
        elif self.model_type == 'linear_svm':
            C = 1.
            if 'C' in model_hyperparams: C = model_hyperparams['C']
            penalty = 'l2'
            if 'penalty' in model_hyperparams: penalty = model_hyperparams['penalty']
            new_model = svm.LinearSVC(C=C, penalty = penalty, class_weight='balanced', loss = 'squared_hinge', dual=False,  max_iter=1000, tol=1.E-3)
        elif self.model_type == 'linear_svm_hinge':
            C = 1.
            if 'C' in model_hyperparams: C = model_hyperparams['C']
            penalty = 'l2'
            new_model = svm.LinearSVC(C=C, penalty = penalty, class_weight='balanced', loss = 'hinge', dual=True,  max_iter=1000, tol=1.E-3)
        elif self.model_type == 'random_forest':
            n_estimators = 10
            if 'n_estimators' in model_hyperparams: C = model_hyperparams['n_estimators']
            new_model = RandomForestClassifier(n_estimators=n_estimators, max_features=None, random_state=1)
        elif self.model_type == 'd_tree':
            new_model = tree.DecisionTreeClassifier(random_state=1)
        elif self.model_type == 'knn':
            n_neighbors=5
            weights = 'distance'
            if 'n_neighbors' in model_hyperparams: n_neighbors = model_hyperparams['n_neighbors']
            if 'weights' in model_hyperparams: weights = model_hyperparams['weights']
            new_model = KNeighborsClassifier(n_neighbors=n_neighbors, weights=weights, n_jobs=-1)
        else:
            raise ValueError('Unrecognized model type: {}'.format(self.model_type))
        return new_model

    def build_sgd_model(self,model_hyperparams={}):
        alpha = 1.E-4
        if 'alpha' in model_hyperparams: alpha = model_hyperparams['alpha']
        l1_ratio = 0.15 
        if 'l1_ratio' in model_hyperparams: l1_ratio = model_hyperparams['l1_ratio']
        new_model = linear_model.SGDClassifier(
                alpha=alpha, loss='log', penalty='elasticnet', l1_ratio=l1_ratio,
                max_iter=1000, tol=1.E-3, class_weight='balanced')
        return new_model

    def predict(self,data):
        """Run predictions for input array-like `data`.

        Each row of `data` represents one sample.
        The `data` columns are assumed to match self.features.

        Parameters
        ----------
        data : array-like
        
        Returns
        -------
        preds : array
        """
        if self.trained and data.shape[0]>0:
            X = self.scaler.transform(data)
            preds = self.model.predict(X)
            try: # not all models have predict_proba()
                certs = self.model.predict_proba(X)
            except:
                certs = np.zeros(data.shape[0])
        else:
            preds = np.array([self.default_val]*data.shape[0])
            certs = np.zeros(data.shape[0])
        return preds, certs 

    def cv_report(self,data,y_true,y_pred):
        all_labels = data[self.target].unique().tolist()
        cm = confusion_matrix(y_true, y_pred, all_labels)
        if len(all_labels) == 2 and isinstance(all_labels[0], bool): 
            score_type = "binary"
        else: 
            score_type = "macro" #self.metric is f1_macro, so we cannot it use directly
        result = dict(
            all_labels = all_labels,
            confusion_matrix = str(cm),
            f1 = f1_score(y_true,y_pred,labels=all_labels,average=score_type),
            precision = precision_score(y_true, y_pred, average=score_type),
            recall = recall_score(y_true, y_pred, average=score_type),
            accuracy = accuracy_score(y_true, y_pred, sample_weight=None)
            )
        #print('f1: {}'.format(result['f1_score']))
        if "f1" in self.metric: 
            result['minimization_score'] = -1*result['f1']
        elif "prec" in self.metric: 
            result['minimization_score'] = -1*result['precision']
        elif "rec" in self.metric: 
            result['minimization_score'] = -1*result['recall']
        else: 
            result['minimization_score'] = -1*result['accuracy']
        return result

    def group_by_pc1(self,dataframe,feature_names,n_groups=5):
        label_cts = dataframe[self.target].value_counts()
        group_ids = pd.Series(np.zeros(dataframe.shape[0]),index=dataframe.index,dtype=int)
        # to check if we have at least 2 different labels:
        if len(label_cts) < 2: return group_ids, False
        labels = list(label_cts.keys())
        for l in labels:
            if label_cts[l] < n_groups:
                # this label cannot be spread across the groups:
                # remove it from the model entirely 
                label_cts.pop(l)
        # to check if we still have at least 2 different labels:
        if len(label_cts) < 2: return group_ids, False
        groups_possible = self._diverse_groups_possible(dataframe,n_groups,len(label_cts.keys()))
        if not groups_possible: return group_ids, False

        gids = range(1,n_groups+1)
        for label in label_cts.keys():
            lidx = dataframe.loc[:,self.target]==label
            ldata = dataframe.loc[lidx,feature_names]
            pc1 = PCA(n_components=1)
            ldata_pc = pc1.fit_transform(ldata).ravel()
            pc_rank = np.argsort(ldata_pc)
            lgroups = np.zeros(ldata.shape[0])
            gp_size = [int(round(ldata.shape[0]/n_groups))] * n_groups
            if ldata.shape[0]%n_groups != 0:
                for i in range(ldata.shape[0]%n_groups):
                    gp_size[i]+=1
            s = 0
            for igid,gid in enumerate(gids):
                lgroups[pc_rank[s:s+gp_size[igid]]] = int(gid)
                s+=gp_size[igid]
            group_ids.loc[lidx] = lgroups
        return group_ids, True

    def print_confusion_matrix(self):
        result = ''
        matrix = self.cross_valid_results['confusion_matrix'].split('\n')
        for ilabel,label in enumerate(self.cross_valid_results['all_labels']):
            result += (matrix[ilabel]+"  "+str(label)+'\n')
        return result

    def get_cv_summary(self):
        return dict(model_type=self.model_type,
                    scores={k:self.cross_valid_results.get(k,None) for k in ['f1','accuracy','precision','recall']})

    def print_CV_report(self):
        """Return a string describing the model's cross-validation metrics.

        Returns
        -------
        CV_report : str
            string with formatted results of cross validation.
        """
        # TODO: document the computation of these metrics, 
        # then refer to documentation in this report
        # TODO: add sample_ids and groupings to this report 
        # TODO: add feature names to this report
        CV_report = 'Cross validation results for {} Classifier\n\n'.format(self.target) + \
            'Confusion matrix:\n' + \
            self.print_confusion_matrix()+'\n\n' + \
            'F1 score: {}\n\n'.format(
            self.cross_valid_results['f1']) + \
            'Precision: {}\n\n'.format(
            self.cross_valid_results['precision']) + \
            'Recall: {}\n\n'.format(
            self.cross_valid_results['recall']) + \
            'Accuracy: {}\n\n'.format(
            self.cross_valid_results['accuracy']) 
        return CV_report

