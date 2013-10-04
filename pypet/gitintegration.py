__author__ = 'Robert Meyer'

from pypet.storageservice import HDF5StorageService
import time

def add_commit_variables(traj, new_commit, repo_folder, message):

    git_hexhsa= 'hexsha'
    git_name_rev = 'name_rev'
    git_repository = 'repository'
    git_committed_date = 'committed_date'
    git_time = 'time'
    git_message = 'message'

    git_time_value = time.strftime('%Y_%m_%d_%Hh%Mm%Ss', time.gmtime(new_commit.committed_date))

    git_commit_name = 'commit_%s_' % str( new_commit.hexsha[0:7])
    git_commit_name = 'git.' + git_commit_name + git_time_value +'.'




    hex=traj.f_add_config(git_commit_name+git_hexhsa, new_commit.hexsha,
                          comment='SHA-1 hash of commit')

    rev=traj.f_add_config(git_commit_name+git_name_rev, new_commit.name_rev,
            comment='String describing the commits hex sha based on the closest Reference')

    repo=traj.f_add_config(git_commit_name+git_repository, repo_folder,
                      comment='Path to the folder with the .git directory.')

    date=traj.f_add_config(git_commit_name+git_committed_date,
                           new_commit.committed_date, comment='Date of commit')

    formatted_time=traj.f_add_config(git_commit_name+git_time,
                           git_time_value,
                           comment='Date of commit in human readable format.')

    msg = traj.f_add_config(git_commit_name+git_message, message,
                            comment='The commit message')


    traj.f_store_items([hex,rev,repo,date,formatted_time,msg])

def make_git_commit(environment, git_repository, user_message):
    ''' Makes a commit returns True in case of Success otherwise False.
    '''

    import git


    repo = git.Repo(git_repository)
    index = repo.index

    traj = environment.v_trajectory

    explore_str = ''
    for param in traj._explored_parameters.values():
        arraystr = HDF5StorageService._all_get_array_str(param, environment._logger)
        explore_str = explore_str + '`%s` explores `%s`; ' %\
                (param.v_name, arraystr)

    if traj.v_comment:
        commentstr = 'Comment: `%s`,' % traj.v_comment
    else:
        commentstr = ''

    if user_message:
       user_message += ' -- '

    message = '%sTrajectory: `%s`, Time: `%s`, %s Explored Parameters: %s' % \
              (user_message,traj.v_name, traj.v_time, commentstr, explore_str)


    repo.git.add('-u')
    new_commit = index.commit(message)
    add_commit_variables(traj,new_commit, git_repository, message)





    return True