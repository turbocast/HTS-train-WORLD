import numpy as np
import ip_utils
from scipy.special import gamma
from scipy.ndimage.filters import gaussian_filter
from scipy.stats import chi2
from mpl_toolkits.mplot3d import Axes3D
from math import ceil
from scipy import linalg
from sklearn.neighbors import NearestNeighbors
from sklearn import linear_model
from utilities import *
from numpy.polynomial import polynomial as P
from parallelization import *
import itertools
import scipy.spatial as spatial
import lowess as lo
import cyflann
import time
from utilities import *

class loess():
    def __init__(self):
        """
        Locally smoothed regression with the LOESS algorithm.
        """
        return None
    
    def single_voxel_fit(self, i):
        """
        Internal parallalized function. Conducts the acutal local optimization.
        """
        weights = self.delta[self.indices[i]] * self.w[i]        
        
        xx = np.concatenate((np.ones((self.r, 1)), self.x[self.indices[i]]), axis=1)
        xx = np.array([np.prod(xx[:, j], axis=1) for j in self.permutation_indeces]).T    

        dot_product = np.dot(xx.T, np.diag(weights))
        b = np.dot(dot_product, self.y[self.indices[i]])
        A = np.dot(dot_product, xx)
        try:
            beta = linalg.solve(A, b)
        except np.linalg.linalg.LinAlgError:
            beta = np.zeros(xx[0].shape)

        yest = np.dot(xx[0], beta)
        return yest
    
    def fit(self, x, y, f=0.005, iterr=3, order=1):
        """
        Locally smoothed regression with the LOWESS algorithm.

        Parameters
        ----------
        x: float [n, dim] array  
            Values of x for which f(x) is known (e.g. measured). The shape of this
            is (n, dim), where dim is the number the dimensions and n is the
            number of distinct coordinates sampled.
    
        y: float [n, ] array
            The known values of f(x) at these points. This has shape (n,) 

        f: int
            bandwidth or smoothing parameter. Determines how much of the data is used
            to fit each local polynomial. 0.1 means 10% of the data is used to fit a
            single data point. Default: 0.005
        
        iterr: int
            Determines how often a robust weighted fit is conducted.
            iterr > 1: aapply the robustification procedure from [Cleveland79], page 831
            Default: 3

        order: int
            The degree of smoothing functions. 1 is locally linear, 2 locally quadratic,
            etc. Default: 1
        """
        self.x = x
        self.y = y
        
        n = y.size
        x_dim = x.shape[-1]
        self.r = int(ceil(f * n))
        
        timer = time.time()
        X = x
        #nbrs = NearestNeighbors(n_neighbors=self.r, algorithm='ball_tree', n_jobs=-1).fit(X)
        #distances, self.indices = nbrs.kneighbors(X)
        #tree = spatial.KDTree(X)
        #distances, self.indices = tree.query(X, k=self.r)
        cy = cyflann.FLANNIndex(algorithm='kdtree_single')
        cy.build_index(X)
        self.indices, distances = cy.nn_index(X, self.r)
        distances = np.sqrt(distances)
        time_for_kNN = time.time() - timer
        print "%0.2fsec needed for kNN" % time_for_kNN
        
        self.w = np.clip(distances/distances[: ,-1][:, None], 0.0, 1.0)
        self.w = (1 - self.w ** 3) ** 3
        
        positions = [range(x_dim+1)]*order
        permutations =  list(itertools.product(*positions))
        sorted_permutations = [sorted(a) for a in permutations]
        self.permutation_indeces = [list(b) for b in set(tuple(b) for b in sorted_permutations)]
        self.permutation_indeces.sort()

        yest = np.zeros(n)
        self.delta = np.ones(n)
        for iteration in range(iterr):

            # Process each voxel        
            p = parallelization(display=True)
            yest_list = p.start(self.single_voxel_fit, n, range(n))
            yest = np.asarray(yest_list)
            
            residuals = y - yest
            s = np.median(np.abs(residuals))
            self.delta = np.clip(residuals / (6.0 * s), -1, 1)
            self.delta = (1 - self.delta ** 2) ** 2

        return yest