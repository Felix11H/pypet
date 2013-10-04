'''
Created on 03.06.2013

@author: robert
'''

from pypet.mplogging import StreamToLogger
from pypet.trajectory import Trajectory, SingleRun
import os
import sys
import logging
try:
    import cPickle as pickle
except:
    import pickle
import multiprocessing as multip
import traceback
from pypet.storageservice import HDF5StorageService, QueueStorageServiceSender,QueueStorageServiceWriter, LockWrapper
from  pypet import globally
from pypet.gitintegration import make_git_commit

def _single_run(args):

    try:
        traj=args[0] 
        log_path=args[1] 
        queue=args[2]
        runfunc=args[3] 
        total_runs = args[4]
        multiproc = args[5]
        runparams = args[6]
        kwrunparams = args[7]
    
        assert isinstance(traj, SingleRun)
        root = logging.getLogger()
        idx = traj.v_idx
        #If the logger has no handler, add one:
        #print root.handlers

        if multiproc:
            
            #print 'do i come here?'
            pid = os.getpid()
            filename = 'process_%s.txt' % str(pid)
            filename=log_path+'/'+filename
            exists = os.path.isfile(filename)

            if not exists:

                h=logging.FileHandler(filename=filename)
                f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
                h.setFormatter(f)
                root.addHandler(h)

                #Redirect standard out and error to the file
                outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
                sys.stdout = outstl

                errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
                sys.stderr = errstl
            
            
        outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
        sys.stdout = outstl

        ## Add the queue for storage
        if not queue == None:
            traj.v_storage_service.queue = queue
    
        root.info('\n--------------------------------\n '
                  'Starting single run #%d of %d '
                  '\n--------------------------------\n' % (idx,total_runs))
        result =runfunc(traj,*runparams,**kwrunparams)
        root.info('Evoke Storing (Either storing directly or sending trajectory to queue)')
        traj.f_store()
        traj._finalize()
        root.info('\n--------------------------------\n '
                  'Finished single run #%d of %d '
                  '\n--------------------------------' % (idx,total_runs))
        return result

    except:
        errstr = "\n\n########## ERROR ##########\n"+"".join(traceback.format_exception(*sys.exc_info()))+"\n"
        logging.getLogger('STDERR').error(errstr)
        raise Exception("".join(traceback.format_exception(*sys.exc_info())))

def _queue_handling(handler,log_path):

    filename = 'queue_process.txt'
    filename=log_path+'/'+filename
    root = logging.getLogger()

    h=logging.FileHandler(filename=filename)
    f = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    root.addHandler(h)

    #Redirect standard out and error to the file
    outstl = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO)
    sys.stdout = outstl

    errstl = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR)
    sys.stderr = errstl
    handler.run()

class Environment(object):
    ''' The environment to run a parameter exploration.


    The first thing you usually do is to create and environment object that takes care about
    the running of the experiment and parameter space exploration.

    :param trajectory: String or trajectory instance. If a string is supplied, a novel
                       trajectory is created with that name.


    :param comment: Comment added to the trajectory if a novel trajectory is created.

    :param dynamically_imported_classes:

          If you wrote custom parameters or results
          that need to be loaded
          dynamically during runtime. The module containing the class
          needs to be specified here as a list of classes or strings
          naming classes and there module paths.
          For example:
          `dynamically_imported_classes =
          ['pypet.parameter.PickleParameter',MyCustomParameter]`

          If you only have a single class to import, you do not need
          the list brackets:
          `dynamically_imported_classes = 'pypet.parameter.PickleParameter'`


    :param log_folder: Folder where all log files are stored

    :param use_hdf5: Whether or not to use the standard hdf5 storage service, if False the following
                    arguments below will be ignored.

    :param filename: The name of the hdf5 file

    :param file_title: Title of the hdf5 file (only important if file is created new)

    :param git_repository:

        If your code base is under git version control you can specify where the path
        (relative or absolute) to
        the folder containing the `.git` directory.
        Note in order to use this tool you need GitPython_.
        If you set this path the environment
        will trigger a commit of your code base adding all files that are currently under
        version control.
        Similar to calling `git add -u` and `git commit -m 'My Message'` on the command line.
        The user can specify the commit message, see below. Note that the message
        will be augmented by the name of the trajectory, the comment of the trajectory
        and the explored parameters.

        This will add information about the revision to the trajectory, see below.

    :param git_message:

        Message passed onto git command.


    .. _GitPython: http://pythonhosted.org/GitPython/0.3.1/index.html

    Note that the comment and the dynamically imported classes are only considered if a novel
    trajectory is created. If you supply a trajectory instance, these fields can be ignored.


    The Environment will automatically add some config settings to your trajectory (if they are not
    already present in your trajectory).

    These are the following (all are added under `traj.config` where traj is your trajectory
    object, that you can get via :func:`~pypet.environment.Environment.v_trajectory`).

    * environment.multiproc:

        Whether or not to use multiprocessing. Default is 0 (False). If you use
        multiprocessing, all your data and the tasks you compute
        must be pickable!

    * environment.ncores:

          If multiproc is 1 (True), this specifies the number of processes that will be spawned
          to run your experiment. Note if you use QUEUE mode (see below) the queue process
          is not included in this number and will add another extra process for storing.

    * environment.wrap_mode:

         If multiproc is 1 (True), specifies how storage to disk is handled via
         the storage service.

         There are two options:

         :const:`~pypet.globally.WRAP_MODE_QUEUE`: ('QUEUE')

         Another process for storing the trajectory is spawned. The sub processes
         running the individual single runs will add their results to a
         multiprocessing queue that is handled by an additional process.
         Note that this requires additional memory since single runs
         will be pickled and send over the queue for storage!


         :const:`~pypet.globally.WRAP_MODE_LOCK`: ('LOCK')

         Each individual process takes care about storage by itself. Before
         carrying out the storage, a lock is placed to prevent the other processes
         to store data. Accordingly, sometimes this leads to a lot of processes
         waiting until the lock is released.
         Yet, single runs do not need to be pickled before storage!

        If you don't want wrapping at all use :const:`~pypet.globally.WRAP_MODE_NONE` ('NONE')


    * environment.continuable:

        Whether the environment should take special care to allow to resume or continue
        crashed trajectories. Default is 1 (True).
        Everything must be pickable in order to allow
        continuing of trajectories. Assume you run experiments that take
        a lot of time. If during your experiments there is a power failure,
        you can resume your trajectory after the last single run that was still
        successfully stored via your storage service.
        This will create a `.cnt` file in the same folder as your hdf5 file,
        using this you can continue crashed trajectories.
        In order to resume trajectories use
        :func:`~pypet.environment.Environment.f_continue_run`

    * hdf5.filename: The hdf5 filename

    * hdf5.file_title: The hdf5 file title

    * hdf5.overview.XXXXX

        Whether the XXXXXX overview table should be created.
        XXXXXX from ['config','parameters','derived_parameters_trajectory',
        'derived_parameters_runs','derived_parameters_runs_summary',
        'results_trajectory', 'results_runs', 'results_runs_summary',
        'result','explored_parameters'].
        Default is True/1

        Note that these tables create a lot of overhead, if you want small hdf5 files set
        these values to False (0). Most memory is taken by the `results_runs`,
        `derived_parameters_runs` and `explored_parameters_runs` tables.

        the 'XXXXXX_summary' tables give a summary about all results or derived parameters.
        It is assumed that results and derived parameters with equal names in individual runs
        are similar and only the first result or derived parameter that was created
        is shown as an example.

        The summary table can be used in combination with `hdf5.purge_duplicate_comments` to only store
        a single comment for every result with the same name in each run, see below.

    * hdf5.purge_duplicate_comments

        If you add a result via :func:`pypet.trajectory.SingleRun.f_add_result` or a derived
        parameter :func:`pypet.trajectory.SingleRun.f_add_derived_parameter` and
        you set a comment, normally that comment would be attached to each and every instance.
        This can produce a lot of unnecessary overhead if the comment is the same for every
        result over all runs. If `hdf5.purge_duplicate_comments=1` than only the comment of the
        first result or derived parameter instance created in a run is stored or comments
        that differ from this first comment.

        For instance,
        during a single run you call `traj.f_add_result('my_result`,42, comment='Mostly harmless!')`
        and the result will be renamed to `results.run_00000000.my_result`. After storage
        in the node associated with this result in your hdf5 file you will find the comment
        `'Mostly harmless!'`. If you call `traj.f_add_result('my_result',-43, comment='Mostly harmless!')`
        in another run again, let's say run 00000001, the name will be mapped to
        `results.run_00000001.my_result`. But this time the comment will not be saved to disk,
        since `'Mostly harmless!'` is already part of the very first result with the name 'my_result'.
        Note that the comments will be compared and storage will only be discarded if the strings
        are exactly the same.

        Default is True/1

    * hdf5.overview.explored_parameters

            Whether an overview table about the explored parameters is added in each
            single run subgroup.
            Default is True/1

    * hdf5.results_per_run

            Expected results you store per run. If you give a good/correct estimate
            storage to hdf5 file is much faster if you want overview tables.

            Default is 0, i.e. the number of results is not estimated!

    * hdf5.derived_parameters_per_run

          Analogous to the above.

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.hexsha

        The SHA-1 hash of the commit.
        `commit_XXXXXXX_XXXX_XX_XX_XXhXXmXXs` is mapped to the first seven items of the sha hash
        and the formatted data of the commit, e.g. `commit_7ef7hd4_2015_10_21_16h29m00s`

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.name_rev

        String describing the commits hex sha based on the closest Reference

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.repository

        Path to git repository

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.committed_date

        Commit date as Unix Epoch data

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.time

        Formatted time string of commit

    * git.commit_XXXXXXX_XXXX_XX_XX_XXh_XXm_XXs.message

        The commit message




    '''
    def __init__(self, trajectory='trajectory',
                 comment='',
                 dynamically_imported_classes=None,
                 log_folder=None,
                 use_hdf5=True,
                 filename=None,
                 file_title=None,
                 git_repository = None,
                 git_message=''):



        #Acquiring the current time
        if isinstance(trajectory,basestring):
            self._traj = Trajectory(trajectory,
                                    dynamically_imported_classes=dynamically_imported_classes,
                                    comment=comment)
        else:
            self._traj = trajectory


        # Prepare file names and log folder
        if file_title  is None:
            file_title = self._traj.v_name

        if filename is None:
            filename = os.path.join(os.getcwd(),'hdf5','experiment.hdf5')

        if log_folder is None:
            log_folder = os.path.join(os.getcwd(), 'logs')




        # Adding some default configuration
        if not self._traj.f_contains('config.environment.log_path'):
            log_path = os.path.join(log_folder,self._traj.v_name)
            self._traj.f_add_config('environment.log_path', log_path).f_lock()
        else:
            log_path=self._traj.f_get('config.environment.log_path').f_get()


        self._make_logger(log_path)


        storage_service = self._traj.v_storage_service

        if not self._traj.f_contains('config.environment.ncores'):
            self._traj.f_add_config('environment.ncores',1, comment='Number of processors in case of multiprocessing')

        if not self._traj.f_contains('config.environment.multiproc'):
            self._traj.f_add_config('environment.multiproc',0, comment= 'Whether or not to use multiprocessing. If yes'
                                                            ' than everything must be pickable.')


        if not self._traj.f_contains('config.environment.wrap_mode'):
            self._traj.f_add_config('environment.wrap_mode',globally.WRAP_MODE_LOCK,
                                    comment ='Multiprocessing mode (if multiproc), '
                                             'i.e. whether to use QUEUE '
                                             'or LOCK'
                                             ' for thread/process safe storing.'
                                             'If you do not want wrap the storage service'
                                             ' use wrap_mode=NONE')



        if not self._traj.f_contains('config.environment.continuable'):
            self._traj.f_add_config('environment.continuable', 1, comment='Whether or not a continue file should'
                                                              ' be created. If yes, everything must be'
                                                              ' pickable.')

        self._use_hdf5 = use_hdf5

        if self._use_hdf5:
            for config_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():

                if not self._traj.f_contains(config_name):
                    self._traj.f_add_config(config_name,1,comment='Whether or not to have an overview '
                                                                  'table with that name.')

            if not self._traj.f_contains('config.hdf5.overview.explored_parameters_runs'):
                self._traj.f_add_config('hdf5.overview.explored_parameters_runs',1,
                                        comment='If there are overview tables about the '
                                                'explored parameters in each run.')

            if not self._traj.f_contains('config.hdf5.purge_duplicate_comments'):
                self._traj.f_add_config('hdf5.purge_duplicate_comments',1,'Whether comments of results and'
                                                            ' derived parameters should only'
                                                            'be stored for the very first instance.'
                                                            ' Works only if the summary tables are'
                                                            ' active.')

            if not self._traj.f_contains('config.hdf5.filename') :
                self._traj.f_add_config('hdf5.filename',filename, comment='Name of hdf5 file')

            if not self._traj.f_contains('config.hdf5.file_title'):
                self._traj.f_add_config('hdf5.file_title', file_title, comment='Title of hdf5 file')

            if not self._traj.f_contains('config.hdf5.results_per_run'):
                self._traj.f_add_config('hdf5.results_per_run', 0,
                                        comment='Expected number of results per run,'
                                            ' a good guess can increase storage performance.')

            if not self._traj.f_contains('config.hdf5.derived_parameters_per_run'):
                self._traj.f_add_config('hdf5.derived_parameters_per_run', 0,
                                        comment='Expected number of derived parameters per run,'
                                            ' a good guess can increase storage performance.')



            self._add_hdf5_storage_service()

        self._git_repository = git_repository
        self._git_message=git_message


        self._logger.info('Environment initialized.')


    def _make_logger(self,log_path):
        if not os.path.isdir(log_path):
            os.makedirs(log_path)

        if len(logging.getLogger().handlers)==0:
            logging.basicConfig(level=logging.INFO)

        f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
        h=logging.FileHandler(filename=log_path+'/main.txt')
        #sh = logging.StreamHandler(sys.stdout)
        root = logging.getLogger()
        root.addHandler(h)

        h=logging.FileHandler(filename=log_path+'/warnings_and_errors.txt')
        #sh = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.WARNING)
        root = logging.getLogger()
        root.addHandler(h)

        for handler in root.handlers:
            handler.setFormatter(f)
        self._logger = logging.getLogger('pypet.environment.Environment')


    def f_switch_off_large_overview(self):
        ''' Switches the tables comsuming the most memory off.

            * Result Overview

            * Derived Parameter Overview

            * Explored Parameter Overview in each Single Run
        '''
        self._traj.config.hdf5.overview.results_runs=0
        self._traj.config.hdf5.overview.derived_parameters_runs = 0
        self._traj.config.hdf5.overview.explored_parameters_runs = 0


    def f_switch_off_all_overview(self):
        ''' Switches all overview tables off and switches off `purge_duplicate_comments`.
        '''
        self._traj.config.hdf5.overview.parameters = 0
        self._traj.config.hdf5.overview.config=0
        self._traj.config.hdf5.overview.explored_parameters=0
        self._traj.config.hdf5.overview.derived_parameters_trajectory=0
        self._traj.config.hdf5.overview.derived_parameters_runs_summary=0
        self._traj.config.hdf5.overview.results_trajectory=0
        self._traj.config.hdf5.overview.results_runs_summary=0
        self._traj.config.hdf5.purge_duplicate_comments=0
        self.f_switch_off_large_overview()

    def f_continue_run(self, continuefile):
        ''' Resume crashed trajectories by supplying the '.cnt' file.
        '''

        continue_dict = pickle.load(open(continuefile,'rb'))
        runfunc = continue_dict['runfunc']
        args = continue_dict['args']
        kwargs = continue_dict['kwargs']
        self._traj = continue_dict['trajectory']
        self._traj.v_full_copy = continue_dict['full_copy']
        self._traj.f_load(load_parameters=globally.LOAD_NOTHING,
             load_derived_parameters=globally.LOAD_NOTHING,
             load_results=globally.LOAD_NOTHING)


        self._traj._remove_incomplete_runs()
        self._do_run(runfunc,*args,**kwargs)



    @ property
    def v_trajectory(self):
        ''' The trajectory of the Environment
        '''
        return self._traj

    def _add_hdf5_storage_service(self):
        ''' Adds the standard HDF5 storage service to the trajectory.

        See also :class:`pypet.storageservice.HDF5StorageService`
        '''
        self._storage_service = HDF5StorageService(self._traj.f_get('config.hdf5.filename').f_get(),
                                                 self._traj.f_get('config.hdf5.file_title').f_get() )

        self._traj.v_storage_service=self._storage_service

    def f_run(self, runfunc, *args,**kwargs):
        ''' Runs the experiments and explores the parameter space.

        :param runfunc: The task or job to do

        :param args: Additional arguments (not the ones in the trajectory) passed to runfunc

        :param kwargs:  Additional keyword arguments (not the ones in the trajectory) passed to runfunc

        :return:

                Iterable over the results returned by runfunc.

                (Not over results stored in the trajectory!
                In order to do that simply interact with the trajectory object, potentially after
                calling`~pypet.trajectory.Trajectory.f_update_skeleton` and loading all results.)

        '''

        continuable = self._traj.f_get('config.environment.continuable').f_get()
        log_path = self._traj.f_get('config.environment.log_path').f_get()

        if self._use_hdf5:
            if ( (not self._traj.f_get('results_runs_summary').f_get() or
                        not self._traj.f_get('results_runs_summary').f_get()) and
                    self._traj.f_get('purge_duplicate_comments').f_get()):
                    raise RuntimeError('You can only use the reduce comments if you enable '
                                       'the summary tables.')

        self._traj._prepare_experiment()

        if continuable:
            #HERE!
            dump_dict ={}
            if 'config.hdf5.filename' in self._traj:
                filename = self._traj.f_get('config.hdf5.filename').f_get()
                #dump_dict['filename'] = filename
                dumpfolder= os.path.split(filename)[0]

                # Make folder if not existing, can happen if Non standard service is used
                if not os.path.isdir(dumpfolder):
                    os.mkdir(dumpfolder)

                dumpfilename=os.path.join(dumpfolder,self._traj.v_name+'.cnt')
            else:
                dumpfilename = os.path.join(log_path,self._traj.v_name+'.cnt')

            prev_full_copy = self._traj.v_full_copy
            dump_dict['full_copy'] = prev_full_copy
            #dump_dict['dump_filename'] = dumpfilename
            #dump_dict['storage_service'] = self._storage_service
            dump_dict['runfunc'] = runfunc
            dump_dict['args'] = args
            dump_dict['kwargs'] = kwargs
            #dump_dict['filename'] = filename
            self._traj.v_full_copy=True
            dump_dict['trajectory'] = self._traj


            pickle.dump(dump_dict,open(dumpfilename,'wb'))

            self._traj.v_full_copy=prev_full_copy

        self._do_run(runfunc,*args,**kwargs)


    def _do_run(self, runfunc, *args, **kwargs):

        if self._git_repository is not None:
            make_git_commit(self,self._git_repository, self._git_message)

        log_path = self._traj.f_get('config.environment.log_path').f_get()
        multiproc = self._traj.f_get('config.environment.multiproc').f_get()
        mode = self._traj.f_get('config.environment.wrap_mode').f_get()

        self._storage_service = self._traj.v_storage_service

        if multiproc and mode != globally.WRAP_MODE_NONE:

            if mode == globally.WRAP_MODE_QUEUE:
                manager = multip.Manager()
                queue = manager.Queue()
                self._logger.info('Starting the Storage Queue!')
                queue_writer = QueueStorageServiceWriter(self._storage_service,queue)

                queue_process = multip.Process(name='QueueProcess',target=_queue_handling, args=(queue_writer,log_path))
                #queue_process.daemon=True
                queue_process.start()

                queue_sender = QueueStorageServiceSender()
                queue_sender.queue=queue
                self._traj.v_storage_service=queue_sender

            elif mode == globally.WRAP_MODE_LOCK:
                manager = multip.Manager()
                lock = manager.Lock()
                queue = None

                lock_wrapper = LockWrapper(self._storage_service,lock)
                self._traj.v_storage_service=lock_wrapper

            else:
                raise RuntimeError('The mutliprocessing mode %s, you chose is not supported, use %s or %s.'
                                    %(globally.WRAP_MODE_QUEUE, globally.WRAP_MODE_LOCK))


            ncores =  self._traj.f_get('config.ncores').f_get()
            
            mpool = multip.Pool(ncores)

            self._logger.info('\n*****************************************************************'
                              '************************************\n'
                              'STARTING runs of trajectory >>%s<< in parallel with %d cores.'
                              '\n*****************************************************************'
                              '************************************\n' %
                              (self._traj.v_name, ncores))
            
            iterator = ((self._traj._make_single_run(n), log_path, queue, runfunc, len(self._traj),
                         multiproc, args, kwargs) for n in xrange(len(self._traj))
                                                            if not self._traj.f_is_completed(n))


            # iterator = self.task_iterator( log_path, queue, runfunc, multiproc, args, kwargs)

            results = mpool.imap(_single_run,iterator)

            
            mpool.close()
            mpool.join()

            if mode == globally.WRAP_MODE_QUEUE:
                self._traj.v_storage_service.send_done()
                queue_process.join()

            mpool.terminate()


            self._traj.v_storage_service=self._storage_service
            self._traj._finalize()

            self._logger.info('\n*****************************************************************'
                              '***************************************************\n'
                              'FINISHED all runs of trajectory >>%s<< in parallel with %d cores.'
                              '\n*****************************************************************'
                              '***************************************************\n' %
                              (self._traj.v_name, ncores))

            return results
        else:

            self._logger.info('\n*****************************************************************'
                              '*********************************************\n'
                              'STARTING runs of trajectory >>%s<<.'
                              '\n*****************************************************************'
                              '*********************************************\n' %
                              self._traj.v_name)
            
            results = [_single_run((self._traj._make_single_run(n),log_path,None,runfunc,
                                    len(self._traj),multiproc,args,kwargs)) for n in xrange(len(self._traj))
                                    if not self._traj.f_is_completed(n)]

            self._traj._finalize()

            self._logger.info('\n*****************************************************************'
                              '*********************************************\n'
                              'FINISHED all runs of trajectory >>%s<<.'
                              '\n*****************************************************************'
                              '*********************************************\n' %
                              self._traj.v_name)

            return results
                
        
        

    # def task_iterator(self,log_path,queue,runfunc,multiproc,args,kwargs):
    #
    #     for n in xrange(len(self._traj)):
    #         if not self._traj.f_is_completed(n):
    #             res_tuple=(self._traj._make_single_run(n), log_path, queue, runfunc, len(self._traj),
    #                 multiproc, args, kwargs)
    #             print res_tuple
    #             yield res_tuple