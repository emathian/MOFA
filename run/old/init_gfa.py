
# Class to iniailise the (non-sparse) GFA model
class init_GFA(initModel):
    def __init__(self, dim, data, lik):
        initModel.__init__(self, dim, data, lik)

    def initZ(self, type="random"):
        # Method to initialise the latent variables
        #  type (str): random, orthogonal, pca

        if type == "random":
            Z_qmean = stats.norm.rvs(loc=0, scale=1, size=(self.N,self.K))
        elif type == "orthogonal":
            print "Not implemented"
            exit()
        elif type == "pca":
            pca = sklearn.decomposition.PCA(n_components=self.K, copy=True, whiten=True)
            tmp = s.concatenate(self.data,axis=0).T
            pca.fit(tmp)
            Z_qmean = pca.components_.T

        Z_qcov = s.repeat(s.eye(self.K)[None,:,:],self.N,0)
        self.Z = gfa.Z_Node(dim=(self.N,self.K), qmean=Z_qmean, qcov=Z_qcov)
        self.Z.updateExpectations()

    def initW(self, type="random"):
        # Method to initialise the weights of the ARD prior
        #  type (str): random, pca
        W_list = [None]*self.M
        for m in xrange(self.M):
            if type == "random":
                W_qmean = stats.norm.rvs(loc=0, scale=1, size=(self.D[m],self.K))
            elif type == "pca":
                print "Not implemented"
                exit()
            W_qcov = s.repeat(a=s.eye(self.K)[None,:,:], repeats=self.D[m] ,axis=0)
            W_list[m] = gfa.W_Node(dim=(self.D[m],self.K), qmean=W_qmean, qcov=W_qcov, qE=W_qmean)
        self.W = Multiview_Variational_Node(self.M, *W_list)

    def initAlpha(self, pa=1e-14, pb=1e-14, qb=1., qE=1.):
        # Method to initialise the precision of the group-wise ARD prior
        # Inputs:
        #  pa (float): 'a' parameter of the prior distribution
        #  pb (float): 'b' parameter of the prior distribution
        #  qb (float): initialisation of the 'b' parameter of the variational distribution
        #  qE (float): initial expectation of the variational distribution
        alpha_list = [None]*self.M
        qb = s.ones(self.K)*qb
        qE = s.ones(self.K)*qE
        for m in xrange(self.M):
            qa = pa + s.ones(self.K)*self.D[m]/2
            alpha_list[m] = gfa.Alpha_Node(dim=(self.K,), pa=pa, pb=pb, qa=qa, qb=s.ones(self.K)*qb, qE=s.ones(self.K)*qE)
        self.Alpha = Multiview_Variational_Node((self.K,)*self.M, *alpha_list)

    def initTau(self, pa=1e-14, pb=1e-14, qb=0., qE=100.):
        # Method to initialise the precision of the noise
        # Inputs:
        #  pa (float): 'a' parameter of the prior distribution
        #  pb (float): 'b' parameter of the prior distribution
        #  qb (float): initialisation of the 'b' parameter of the variational distribution
        #  qE (float): initial expectation of the variational distribution
        tau_list = [None]*self.M
        for m in xrange(self.M):
            if self.lik[m] == "poisson":
                tmp = 0.25 + 0.17*s.amax(self.data[m],axis=0) 
                tau_list[m] = Observed_Local_Node(dim=(self.D[m],), value=tmp)
            elif self.lik[m] == "bernoulli":
                tmp = s.ones(self.D[m])*0.25 
                tau_list[m] = Observed_Local_Node(dim=(self.D[m],), value=tmp)
            elif self.lik[m] == "binomial":
                tmp = 0.25*s.amax(self.data["tot"][m],axis=0)
                tau_list[m] = Observed_Local_Node(dim=(self.D[m],), value=tmp)
            elif self.lik[m] == "gaussian":
                qa = pa + s.ones(self.D[m])*self.N/2
                qb = s.zeros(self.D[m]) + qb
                qE = s.zeros(self.D[m]) + qE
                tau_list[m] = gfa.Tau_Node(dim=(self.D[m],), pa=pa, pb=pb, qa=qa, qb=qb, qE=qE)
        self.Tau = Multiview_Mixed_Node(self.M,*tau_list)

    def initY(self):
        # Method to initialise the observed data
        Y_list = [None]*self.M
        for m in xrange(self.M):
            if self.lik[m]=="gaussian":
                Y_list[m] = gfa.Y_Node(dim=(self.N,self.D[m]), obs=self.data[m])
            elif self.lik[m]=="poisson":
                Y_list[m] = Poisson_PseudoY_Node(dim=(self.N,self.D[m]), obs=self.data[m], E=None)
            elif self.lik[m]=="bernoulli":
                Y_list[m] = Bernoulli_PseudoY_Node(dim=(self.N,self.D[m]), obs=self.data[m], E=None)
            elif self.lik[m]=="binomial":
                Y_list[m] = Binomial_PseudoY_Node(dim=(self.N,self.D[m]), tot=data["tot"][m], obs=data["obs"][m], E=None)
        self.Y = Multiview_Mixed_Node(self.M, *Y_list)

    def MarkovBlanket(self):
        # Method to define the Markov Blankets
        self.Z.addMarkovBlanket(W=self.W, tau=self.Tau, Y=self.Y)
        for m in xrange(self.M):
            self.Alpha.nodes[m].addMarkovBlanket(W=self.W.nodes[m])
            self.W.nodes[m].addMarkovBlanket(Z=self.Z, tau=self.Tau.nodes[m], alpha=self.Alpha.nodes[m], Y=self.Y.nodes[m])
            self.Y.nodes[m].addMarkovBlanket(Z=self.Z, W=self.W.nodes[m], tau=self.Tau.nodes[m])
            self.Tau.nodes[m].addMarkovBlanket(W=self.W.nodes[m], Z=self.Z, Y=self.Y.nodes[m])
