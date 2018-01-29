from collections import OrderedDict

from . import saxs_math, saxs_fit

from citrination_client import CitrinationClient

class CitrinationSaxsModels(object):
    """A set of models that uses Citrination to evaluate SAXS spectra.

    Use of this class requires a Citrination api key.
    You can get one by making an account on Citrination.
    The api key should be copy/pasted into a file,
    and the path to the file should be provided
    as an instantiation argument.
    """

    def __init__(self, api_key_file, address='https://citrination.com/'):
        with open(api_key_file, "r") as g:
            api_key = g.readline()
        a_key = api_key.strip()

        self.client = CitrinationClient(site = address, api_key=a_key)


    def classify(self,sample_params):
        """
        Parameters
        ----------
        sample_params : ordered dictionary
            ordered dictionary of floats representing features of test sample

        Returns
        -------
        Returns
        -------
        populations : dict
            dictionary of integers
            counting predicted scatterer populations
            for all populations in saxs_fit.population_keys.
        uncertainties : dict
            dictionary, similar to `populations`,
            but containing the uncertainty of the prediction
        """

        inputs = self.append_str_property(sample_params)

        populations = OrderedDict()
        uncertainties = OrderedDict()
        resp = self.client.predict("24", inputs) # "24" is ID of dataview on Citrination
        for popname in saxs_fit.population_keys:
            populations[popname] = int(resp['candidates'][0]['Property '+popname][0])
            uncertainties[popname] = float(resp['candidates'][0]['Property '+popname][1])

        return populations, uncertainties


    # helper function
    def append_str_property(self, sample_params):
        inputs = {}
        for k,v in sample_params.items():
            k = "Property " + k
            inputs[k] = v
        return inputs


    def predict_params(self,populations,features,q_I, predict_intens_params = True):
        """Use Citrination to predict the scattering parameters.

        Parameters
        ----------
        populations : dict
            dictionary counting scatterer populations,
            similar to output of self.classify()
        features : dict
            dictionary of sample numerical features,
            similar to output of saxs_math.profile_spectrum().
        q_I : array
            n-by-2 array of scattering vector (1/Angstrom) and intensities.
        predict_intens_params : bool
            if True, intensivity parameters are calculated using SaxsFitter

        Returns
        -------
        Returns
        -------
        params : dict
            dictionary of predicted and calculated scattering parameters:
            r0_sphere, sigma_sphere, and rg_gp are predicted using Citrinaion models
            IO_floor and IO_sphere are calculated using SaxsFitter
        """

        features = self.append_str_property(features)

        params = OrderedDict()
        uncertainties = OrderedDict()
        if bool(populations['unidentified']):
            return params, uncertainties

        if bool(populations['spherical_normal']):
            resp = self.client.predict("27", features) # "27" is ID of dataview on Citrination
            params['r0_sphere'] = [float(resp['candidates'][0]['Property r0_sphere'][0])]
            uncertainties['r0_sphere'] = float(resp['candidates'][0]['Property r0_sphere'][1])
            additional_features = saxs_math.spherical_normal_profile(q_I)
            additional_features = self.append_str_property(additional_features)
            ss_features = dict(features)
            ss_features.update(additional_features)
            resp = self.client.predict("28", ss_features)
            params['sigma_sphere'] = [float(resp['candidates'][0]['Property sigma_sphere'][0])]
            uncertainties['sigma_sphere'] = float(resp['candidates'][0]['Property sigma_sphere'][1])

        if bool(populations['guinier_porod']):
            additional_features = saxs_math.guinier_porod_profile(q_I)
            additional_features = self.append_str_property(additional_features)
            rg_features = dict(features)
            rg_features.update(additional_features)
            resp =self.client.predict("29", rg_features)
            params['rg_gp'] = [float(resp['candidates'][0]['Property rg_gp'][0])]
            uncertainties['rg_gp'] = float(resp['candidates'][0]['Property rg_gp'][0])

        if predict_intens_params:
            params['I0_floor'] = [saxs_fit.param_defaults['I0_floor']]
            uncertainties['I0_floor'] = None
            if bool(populations['spherical_normal']):
                params['I0_sphere'] = [saxs_fit.param_defaults['I0_sphere']]
                uncertainties['I0_sphere'] = None
            if bool(populations['guinier_porod']):
                params['G_gp'] = [saxs_fit.param_defaults['G_gp']]
                uncertainties['G_gp'] = None
            if bool(populations['diffraction_peaks']):
                params['I_pkcenter'] = [saxs_fit.param_defaults['I_pkcenter']]
                uncertainties['G_gp'] = None
            sxf = saxs_fit.SaxsFitter(q_I,populations)
            p_fit, rpt = sxf.fit_intensity_params(params)
            params = saxs_fit.update_params(params,p_fit)

        return params,uncertainties
