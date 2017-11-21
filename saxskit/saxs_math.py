"""This module is for evaluating SAXS intensities and related quantities.

SAXS spectra are described by an n-by-2 array
of scattering vector magnitudes (1/Angstrom)
and intensities (arbitrary units).
Computing the theoretical SAXS spectrum requires a dictionary of populations
(states number of distinct groups of each scatterer type)
and a dictionary of parameters
(a set of parameters is expected for each flagged population).

The supported populations and associated parameters are:

    - 'guinier_porod': number of Guinier-Porod scatterers 

      - 'G_gp': Guinier prefactor for Guinier-Porod scatterers 
      - 'rg_gp': radius of gyration for Guinier-Porod scatterers 
      - 'D_gp': Porod exponent for Guinier-Porod scatterers 

    - 'spherical_normal': number of populations of spheres 
        with normal (Gaussian) size distribution 

      - 'I0_sphere': spherical form factor scattering intensity scaling factor
      - 'r0_sphere': mean sphere size (Angstrom) 
      - 'sigma_sphere': fractional standard deviation of sphere size 

    - 'diffraction_peaks': number of Psuedo-Voigt 
        diffraction peaks (not yet supported) 

    - 'unidentified': if not zero, the scattering spectrum is unfamiliar. 
        This causes all populations and parameters to be ignored.

    - Common parameters for all populations:
      
      - 'I0_floor': magnitude of floor term, flat for all q. 
"""
import numpy as np

def compute_saxs(q,populations,params):
    """Compute a SAXS intensity spectrum.

    TODO: Document the equation.

    Parameters
    ----------
    q : array
        Array of q values at which saxs intensity should be computed.
    populations : dict
        Each entry is an integer representing the number 
        of distinct populations of various types of scatterer. 
    params : dict
        Scattering equation parameters. 
        Each entry in the dict may be a float or a list of floats,
        depending on whether there are one or more of the corresponding
        scatterer populations.

    Returns
    ------- 
    I : array
        Array of scattering intensities for each of the input q values
    """
    u_flag = bool(populations['unidentified'])
    pks_flag = bool(populations['diffraction_peaks'])
    I = np.zeros(len(q))
    if not u_flag and not pks_flag:
        n_gp = populations['guinier_porod']
        n_sph = populations['spherical_normal']

        I0_floor = params['I0_floor'] 
        I = I0_floor*np.ones(len(q))

        if n_gp:
            rg_gp = params['rg_gp']
            G_gp = params['G_gp']
            D_gp = params['D_gp']
            if not isinstance(rg_gp,list): rg_gp = [rg_gp]
            if not isinstance(G_gp,list): G_gp = [G_gp]
            if not isinstance(D_gp,list): D_gp = [D_gp]
            for igp in range(n_gp):
                I_gp = guinier_porod(q,rg_gp[igp],D_gp[igp],G_gp[igp])
                I += I_gp

        if n_sph:
            I0_sph = params['I0_sphere']
            r0_sph = params['r0_sphere']
            sigma_sph = params['sigma_sphere']
            if not isinstance(I0_sph,list): I0_sph = [I0_sph]
            if not isinstance(r0_sph,list): r0_sph = [r0_sph]
            if not isinstance(sigma_sph,list): sigma_sph = [sigma_sph]
            for isph in range(n_sph):
                I_sph = spherical_normal_saxs(q,r0_sph[isph],sigma_sph[isph])
                I += I0_sph[isph]*I_sph

    return I

def spherical_normal_saxs(q,r0,sigma):
    """Compute SAXS intensity of a normally-distributed sphere population.

    The returned intensity is normalized 
    such that I(q=0) is equal to 1.
    The current version samples the distribution 
    from r0*(1-5*sigma) to r0*(1+5*sigma) 
    in steps of 0.02*sigma*r0.
    Originally contributed by Amanda Fournier.
    TODO: test distribution sampling, speed up if possible.

    Parameters
    ----------
    q : array
        array of scattering vector magnitudes
    r0 : float
        mean radius of the sphere population
    sigma : float
        fractional standard deviation of the sphere population radii

    Returns
    -------
    I : array
        Array of scattering intensities for each of the input q values
    """
    q_zero = (q == 0)
    q_nz = np.invert(q_zero) 
    I = np.zeros(q.shape)
    if sigma < 1E-9:
        x = q*r0
        V_r0 = float(4)/3*np.pi*r0**3
        I[q_nz] = V_r0**2 * (3.*(np.sin(x[q_nz])-x[q_nz]*np.cos(x[q_nz]))*x[q_nz]**-3)**2
        I_zero = V_r0**2 
    else:
        sigma_r = sigma*r0
        dr = sigma_r*0.02
        rmin = np.max([r0-5*sigma_r,dr])
        rmax = r0+5*sigma_r
        I_zero = 0
        for ri in np.arange(rmin,rmax,dr):
            xi = q*ri
            V_ri = float(4)/3*np.pi*ri**3
            # The normal-distributed density of particles with radius r_i:
            rhoi = 1./(np.sqrt(2*np.pi)*sigma_r)*np.exp(-1*(r0-ri)**2/(2*sigma_r**2))
            I_zero += V_ri**2 * rhoi*dr
            I[q_nz] += V_ri**2 * rhoi*dr*(3.*(np.sin(xi[q_nz])-xi[q_nz]*np.cos(xi[q_nz]))*xi[q_nz]**-3)**2
    if any(q_zero):
        I[q_zero] = I_zero
    I = I/I_zero 
    return I

def guinier_porod(q,r_g,porod_exponent,guinier_factor):
    """Compute the Guinier-Porod small-angle scattering intensity.
    
    Parameters
    ----------
    q : array
        array of q values
    r_g : float
        radius of gyration
    porod_exponent : float
        high-q Porod's law exponent
    guinier_factor : float
        low-q Guinier prefactor (equal to intensity at q=0)

    Returns
    -------
    I : array
        Array of scattering intensities for each of the input q values

    Reference
    ---------
    B. Hammouda, J. Appl. Cryst. (2010). 43, 716-719.
    """
    # q-domain boundary q_splice:
    q_splice = 1./r_g * np.sqrt(3./2*porod_exponent)
    idx_guinier = (q <= q_splice)
    idx_porod = (q > q_splice)
    # porod prefactor D:
    porod_factor = guinier_factor*np.exp(-1./2*porod_exponent)\
                    * (3./2*porod_exponent)**(1./2*porod_exponent)\
                    * 1./(r_g**porod_exponent)
    I = np.zeros(q.shape)
    # Guinier equation:
    if any(idx_guinier):
        I[idx_guinier] = guinier_factor * np.exp(-1./3*q[idx_guinier]**2*r_g**2)
    # Porod equation:
    if any(idx_porod):
        I[idx_porod] = porod_factor * 1./(q[idx_porod]**porod_exponent)
    return I

def profile_spectrum(q_I):
    """Numerical profiling of a SAXS spectrum.

    Profile a saxs spectrum (n-by-2 array q_I) 
    by taking several fast numerical metrics 
    from the measured data.
    The metrics should be consistent for spectra
    with different intensity scaling 
    or different q domains.   

    This method should execute gracefully
    for any n-by-2 input array,
    such that it can be used to profile any type of spectrum. 
    TODO: document the returned metrics here.

    Parameters
    ----------
    q_I : array
        n-by-2 array of scattering vector q and scattered intensity I
    
    Returns
    -------
    params : dict
        dictionary of scattering equation parameters,
        for input to compute_saxs() 
    """ 
    q = q_I[:,0]
    I = q_I[:,1]
    # I metrics
    idxmax = np.argmax(I)
    idxmin = np.argmin(I)
    I_min = I[idxmin]
    I_max = I[idxmax] 
    q_Imax = q[idxmax]
    I_range = I_max - I_min
    #I_sum = np.sum(I)
    I_mean = np.mean(I)
    Imax_over_Imean = I_max/I_mean
    # log(I) metrics
    nz = I>0
    q_nz = q[nz]
    I_nz = I[nz]
    logI_nz = np.log(I_nz)
    logI_max = np.max(logI_nz)
    logI_min = np.min(logI_nz)
    logI_range = logI_max - logI_min
    logI_std = np.std(logI_nz)
    logI_max_over_std = logI_max / logI_std
    # I_max peak shape analysis
    idx_around_max = ((q > 0.9*q_Imax) & (q < 1.1*q_Imax))
    Imean_around_max = np.mean(I[idx_around_max])
    Imax_sharpness = I_max / Imean_around_max

    ### fluctuation analysis
    # array of the difference between neighboring points:
    nn_diff = logI_nz[1:]-logI_nz[:-1]
    # keep indices where the sign of this difference changes.
    # also keep first index
    nn_diff_prod = nn_diff[1:]*nn_diff[:-1]
    idx_keep = np.hstack((np.array([True]),nn_diff_prod<0))
    fluc = np.sum(np.abs(nn_diff[idx_keep]))
    logI_fluctuation = fluc/logI_range

    # TODO: add correlative metrics.

    params = OrderedDict()
    params['q_Imax'] = q_Imax
    params['Imax_over_Imean'] = Imax_over_Imean
    params['Imax_sharpness'] = Imax_sharpness
    params['logI_fluctuation'] = logI_fluctuation
    params['logI_max_over_std'] = logI_max_over_std
    return params 

def fit_I0(q,I,order=4):
    """
    Find an estimate for I(q=0) by polynomial fitting.
    All of the input q, I(q) values are used in the fitting.
    """
    #TODO: add a sign constraint, at least
    I_mean = np.mean(I)
    I_std = np.std(I)
    q_mean = np.mean(q)
    q_std = np.std(q)
    I_s = (I-I_mean)/I_std
    q_s = (q-q_mean)/q_std
    p = fit_with_slope_constraint(q_s,I_s,-1*q_mean/q_std,0,order) 
    I_at_0 = np.polyval(p,-1*q_mean/q_std)*I_std+I_mean

    #from matplotlib import pyplot as plt
    #plt.plot(q,I,'bo')
    #plt.plot([0.],[I_at_0],'ro')
    #plt.plot(q,np.polyval(p,q_s)*I_std+I_mean)
    #q_fill = np.arange(0.,q[-1],float(q[-1])/100)
    #q_s_fill = (q_fill-q_mean)/q_std
    #plt.plot(q_fill,np.polyval(p,q_s_fill)*I_std+I_mean)
    #plt.show()

    return I_at_0,p

def fit_with_slope_constraint(q,I,q_cons,dIdq_cons,order,weights=None):
    """
    Perform a polynomial fitting 
    of the low-q region of the spectrum
    with dI/dq(q=0) constrained to be zero.
    This is performed by forming a Lagrangian 
    from a quadratic cost function 
    and the Lagrange-multiplied constraint function.
    
    TODO: Document cost function, constraints, Lagrangian.

    Inputs q and I are not standardized in this function,
    so they should be standardized beforehand 
    if standardized fitting is desired.
    At the provided constraint point, q_cons, 
    the returned polynomial will have slope dIdq_cons.

    Because of the form of the Lagrangian,
    this constraint cannot be placed at exactly zero.
    This would result in indefinite matrix elements.
    """
    Ap = np.zeros( (order+1,order+1),dtype=float )
    b = np.zeros(order+1,dtype=float)
    # TODO: vectorize the construction of Ap
    for i in range(0,order):
        for j in range(0,order):
            Ap[i,j] = np.sum( q**j * q**i )
        Ap[i,order] = -1*i*q_cons**(i-1)
    for j in range(0,order):
        Ap[order,j] = j*q_cons**(j-1)
        b[j] = np.sum(I*q**j)
    b[order] = dIdq_cons
    p_fit = np.linalg.solve(Ap,b) 
    p_fit = p_fit[:-1]  # throw away Lagrange multiplier term 
    p_fit = p_fit[::-1] # reverse coefs to get np.polyfit format
    #from matplotlib import pyplot as plt
    #plt.figure(3)
    #plt.plot(q,I)
    #plt.plot(q,np.polyval(p_fit,q))
    #plt.plot(np.arange(q_cons,q[-1],q[-1]/100),np.polyval(p_fit,np.arange(q_cons,q[-1],q[-1]/100)))
    #plt.plot(q_cons,np.polyval(p_fit,q_cons),'ro')
    #plt.show()
    return p_fit

def compute_Rsquared(y1,y2):
    """
    Compute the coefficient of determination between input arrays y1 and y2.
    """
    sum_var = np.sum( (y1-np.mean(y1))**2 )
    sum_res = np.sum( (y1-y2)**2 ) 
    return float(1)-float(sum_res)/sum_var

def compute_pearson(y1,y2):
    """
    Compute the Pearson correlation coefficient between input arrays y1 and y2.
    """
    y1mean = np.mean(y1)
    y2mean = np.mean(y2)
    y1std = np.std(y1)
    y2std = np.std(y2)
    return np.sum((y1-y1mean)*(y2-y2mean))/(np.sqrt(np.sum((y1-y1mean)**2))*np.sqrt(np.sum((y2-y2mean)**2)))

def compute_chi2(y1,y2,weights=None):
    """
    Compute the sum of the difference squared between input arrays y1 and y2.
    """
    if weights is None:
        return np.sum( (y1 - y2)**2 )
    else:
        weights = weights / np.sum(weights)
        return np.sum( (y1 - y2)**2*weights )

def saxs_Iq4_metrics(q_I):
    """
    From an input spectrum q and I(q),
    compute several properties of the I(q)*q^4 curve.
    This was designed for spectra that are 
    dominated by a dilute spherical form factor term.
    The metrics extracted by this Operation
    were originally intended as an intermediate step
    for estimating size distribution parameters 
    for a population of dilute spherical scatterers.

    Returns a dict of metrics.
    Dict keys and meanings:
    q_at_Iqqqq_min1: q value at first minimum of I*q^4
    I_at_Iqqqq_min1: I value at first minimum of I*q^4
    Iqqqq_min1: I*q^4 value at first minimum of I*q^4
    pIqqqq_qwidth: Focal q-width of polynomial fit to I*q^4 near first minimum of I*q^4 
    pIqqqq_Iqqqqfocus: Focal point of polynomial fit to I*q^4 near first minimum of I*q^4
    pI_qvertex: q value of vertex of polynomial fit to I(q) near first minimum of I*q^4  
    pI_Ivertex: I(q) at vertex of polynomial fit to I(q) near first minimum of I*q^4
    pI_qwidth: Focal q-width of polynomial fit to I(q) near first minimum of I*q^4
    pI_Iforcus: Focal point of polynomial fit to I(q) near first minimum of I*q^4

    TODO: document the algorithm here.
    """
    q = q_I[:,0]
    I = q_I[:,1]
    d = {}
    #if not dI:
    #    # uniform weights
    #    wt = np.ones(q.shape)   
    #else:
    #    # inverse error weights, 1/dI, 
    #    # appropriate if dI represents
    #    # Gaussian uncertainty with sigma=dI
    #    wt = 1./dI
    #######
    # Heuristics step 1: Find the first local max
    # and subsequent local minimum of I*q**4 
    Iqqqq = I*q**4
    # w is the number of adjacent points to consider 
    # when examining the I*q^4 curve for local extrema.
    # A greater value of w filters out smaller extrema.
    w = 10
    idxmax1, idxmin1 = 0,0
    stop_idx = len(q)-w-1
    test_range = iter(range(w,stop_idx))
    idx = test_range.next() 
    while any([idxmax1==0,idxmin1==0]) and idx < stop_idx-1:
        if np.argmax(Iqqqq[idx-w:idx+w+1]) == w and idxmax1 == 0:
            idxmax1 = idx
        if np.argmin(Iqqqq[idx-w:idx+w+1]) == w and idxmin1 == 0 and not idxmax1 == 0:
            idxmin1 = idx
        idx = test_range.next()
    if idxmin1 == 0 or idxmax1 == 0:
        ex_msg = str('unable to find first maximum and minimum of I*q^4 '
        + 'by scanning for local extrema with a window width of {} points'.format(w))
        d['message'] = ex_msg 
        raise RuntimeError(ex_msg)
    #######
    # Heuristics 2: Characterize I*q**4 around idxmin1, 
    # by locally fitting a standardized polynomial.


    idx_around_min1 = (q>0.9*q[idxmin1]) & (q<1.1*q[idxmin1])
    # keep only the lower-q side, to encourage upward curvature
    #idx_around_min1 = (q>0.8*q[idxmin1]) & (q<q[idxmin1])


    q_min1_mean = np.mean(q[idx_around_min1])
    q_min1_std = np.std(q[idx_around_min1])
    q_min1_s = (q[idx_around_min1]-q_min1_mean)/q_min1_std
    Iqqqq_min1_mean = np.mean(Iqqqq[idx_around_min1])
    Iqqqq_min1_std = np.std(Iqqqq[idx_around_min1])
    Iqqqq_min1_s = (Iqqqq[idx_around_min1]-Iqqqq_min1_mean)/Iqqqq_min1_std
    #Iqqqq_min1_quad = lambda x: np.sum((x[0]*q_min1_s**2 + x[1]*q_min1_s + x[2] - Iqqqq_min1_s)**2)
    #res = scipimin(Iqqqq_min1_quad,[1E-3,0,0],bounds=[(0,None),(None,None),(None,None)])
    #p_min1 = res.x
    p_min1 = np.polyfit(q_min1_s,Iqqqq_min1_s,2,None,False,np.ones(len(q_min1_s)),False)
    # polynomial vertex horizontal coord is -b/2a
    qs_at_min1 = -1*p_min1[1]/(2*p_min1[0])
    d['q_at_Iqqqq_min1'] = qs_at_min1*q_min1_std+q_min1_mean
    # polynomial vertex vertical coord is poly(-b/2a)
    Iqqqqs_at_min1 = np.polyval(p_min1,qs_at_min1)
    d['Iqqqq_min1'] = Iqqqqs_at_min1*Iqqqq_min1_std+Iqqqq_min1_mean
    d['I_at_Iqqqq_min1'] = d['Iqqqq_min1']*float(1)/(d['q_at_Iqqqq_min1']**4)
    # The focal width of the parabola is 1/a 
    p_min1_fwidth = abs(1./p_min1[0])
    d['pIqqqq_qwidth'] = p_min1_fwidth*q_min1_std
    # The focal point is at -b/2a,poly(-b/2a)+1/(4a)
    p_min1_fpoint = Iqqqqs_at_min1+float(1)/(4*p_min1[0])
    d['pIqqqq_Iqqqqfocus'] = p_min1_fpoint*Iqqqq_min1_std+Iqqqq_min1_mean
    #######
    # Heuristics 2b: Characterize I(q) near min1 of I*q^4.
    I_min1_mean = np.mean(I[idx_around_min1])
    I_min1_std = np.std(I[idx_around_min1])
    I_min1_s = (I[idx_around_min1]-I_min1_mean)/I_min1_std
    #I_min1_error = lambda x: np.sum((x[0]*q_min1_s**2 + x[1]*q_min1_s + x[2] - I_min1_s)**2)
    #res = scipimin(I_min1_error,[0,0,0],bounds=[(0,None),(None,None),(None,None)])
    #pI_min1 = res.x
    pI_min1 = np.polyfit(q_min1_s,I_min1_s,2,None,False,np.ones(len(q_min1_s)),False)
    # polynomial vertex horizontal coord is -b/2a
    qs_vertex = -1*pI_min1[1]/(2*pI_min1[0])
    d['pI_qvertex'] = qs_vertex*q_min1_std+q_min1_mean
    # polynomial vertex vertical coord is poly(-b/2a)
    Is_vertex = np.polyval(pI_min1,qs_vertex)
    d['pI_Ivertex'] = Is_vertex*I_min1_std+I_min1_mean
    # The focal width of the parabola is 1/a 
    pI_fwidth = abs(1./pI_min1[0])
    d['pI_qwidth'] = pI_fwidth*q_min1_std
    # The focal point is at -b/2a,poly(-b/2a)+1/(4a)
    pI_fpoint = Is_vertex+float(1)/(4*pI_min1[0])
    d['pI_Ifocus'] = pI_fpoint*I_min1_std+I_min1_mean
    #######
    return d

