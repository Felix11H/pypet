__author__ = 'robert'

import numpy as np
import unittest
from mypet.parameter import Parameter, PickleParameter, BaseResult
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity,cartesian_product
from mypet.environment import Environment
from mypet.storageservice import HDF5StorageService
import pickle
import logging
import cProfile
from mypet.utils.helpful_functions import flatten_dictionary
import scipy.sparse as spsp
import os
import shutil



def simple_calculations(traj, arg1, simple_kwarg):


        all_mat = traj.csc_mat + traj.lil_mat + traj.csr_mat
        Normal_int= traj.Normal.int
        Sum= np.sum(traj.Numpy.double)

        result_mat = all_mat * Normal_int * Sum * arg1 * simple_kwarg
        traj.add_result('ResMatrix',result_mat.todense())
        traj.add_derived_parameter('All.To.String', str(traj.to_dict(fast_access=True,short_names=False)))




class EnvironmentTest(unittest.TestCase):


    def set_mode(self):
        self.mode = 'Normal'
        self.multiproc = False
        self.ncores = 1

    def _create_param_dict(self):
        self.param_dict = {}

        self.param_dict['Normal'] = {}
        self.param_dict['Numpy'] = {}
        self.param_dict['Sparse'] ={}
        self.param_dict['Numpy_2D'] = {}

        normal_dict = self.param_dict['Normal']
        normal_dict['string'] = 'Im a test string!'
        normal_dict['int'] = 42
        normal_dict['double'] = 42.42
        normal_dict['bool'] =True

        numpy_dict=self.param_dict['Numpy']
        numpy_dict['string'] = np.array(['Uno', 'Dos', 'Tres'])
        numpy_dict['int'] = np.array([1,2,3,4])
        numpy_dict['double'] = np.array([1.0,2.0,3.0,4.0])
        numpy_dict['bool'] = np.array([True,False, True])

        self.param_dict['Numpy_2D']['double'] = np.array([[1.0,2.0],[3.0,4.0]])

        spsparse_csc = spsp.csc_matrix((2222,22))
        spsparse_csc[1,2] = 44.6

        spsparse_csr = spsp.csr_matrix((2222,22))
        spsparse_csr[1,3] = 44.7

        spsparse_lil = spsp.lil_matrix((2222,22))
        spsparse_lil[3,2] = 44.5

        self.param_dict['Sparse']['lil_mat'] = spsparse_lil
        self.param_dict['Sparse']['csc_mat'] = spsparse_csc
        self.param_dict['Sparse']['csr_mat'] = spsparse_csr


    def add_params(self,traj):

        flat_dict = flatten_dictionary(self.param_dict,'.')

        for key, val in flat_dict.items():
            traj.ap(key,val)

        traj.adp('Another.String', 'Hi, how are you?')



    def explore(self, traj):
        self.explored = {}
        name1=traj.gfpn('Normal.int')
        self.explored[name1] = [42,43,44]
        name2=traj.gfpn('Numpy.double')
        self.explored[name2] = [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]

        traj.explore(cartesian_product,self.explored)



    def setUp(self):
        self.set_mode()

        logging.basicConfig(level = logging.DEBUG)

        self.filename = '../../Test/HDF5/test.hdf5'
        self.logfolder = '../../Test/Log'
        self.trajname = 'Test'

        env = Environment(self.trajname,self.filename,self.trajname,logfolder=self.logfolder)

        traj = env.get_trajectory()

        traj.multiproc = self.multiproc
        traj.mode = self.mode
        traj.ncores = self.ncores

        traj.set_standard_param_type(PickleParameter)

        ## Create some parameters
        self._create_param_dict()
        ### Add some parameter:
        self.add_params(traj)


        ###Explore
        self.explore(traj)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env

    def test_run(self):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        self.env.run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)


        newtraj = Trajectory()
        newtraj.set_storage_service(HDF5StorageService(filename=self.filename))
        newtraj.load(trajectoryname=-1,load_derived_params=2,load_results=2,replace=True)

        ## Check if everything is fine:


        self.traj.update_skeleton()
        self.traj.load_stuff(self.traj.to_dict().keys(), only_empties=True)

        traj = self.traj

        old_items = traj.to_dict(fast_access=True)
        new_items = newtraj.to_dict(fast_access=True)

        self.assertEqual(len(old_items),len(new_items))
        for key,item in new_items.items():
            old_item = old_items[key]
            if not isinstance(item, BaseResult) and not spsp.issparse(item) and not key in traj.get_explored_params():
               self.assertTrue(np.all(old_item==item),'For key %s: %s not equal to %s' %(key,str(old_item),str(item)))




        #os.remove(self.filename)
        #shutil.rmtree(self.logfolder,True)





if __name__ == '__main__':
    unittest.main()