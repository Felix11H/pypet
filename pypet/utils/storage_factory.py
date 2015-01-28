"""
Module to create storage service from given settings.

Currently only the HDF5StorageService is supported.
But to be extended in the future.

"""

__author__ = 'Robert Meyer'

import inspect
import os

from pypet.utils.helpful_functions import get_matching_kwargs
from pypet.storageservice import HDF5StorageService
import pypet.compat as compat


def _create_storage(storage_service, trajectory=None, **kwargs):
    """Creates a service from a constructor and checks which kwargs are not used"""
    kwargs_copy = kwargs.copy()
    kwargs_copy['trajectory'] = trajectory
    matching_kwargs = get_matching_kwargs(storage_service, kwargs_copy)
    storage_service = storage_service(**matching_kwargs)
    unused_kwargs = set(kwargs.keys()) - set(matching_kwargs.keys())
    return storage_service, unused_kwargs


def storage_factory(storage_service, trajectory=None, **kwargs):
    """Creates a storage service, to be extended if new storage services are added

    :param storage_service:

        Storage Service instance of constructor or a string pointing to a file

    :param trajectory:

        A trajectory instance

    :param kwargs:

        Arguments passed to the storage service

    :return:

        A storage service and a set of not used keyword arguments from kwargs

    """
    if isinstance(storage_service, compat.base_type) and 'filename' not in kwargs:
        kwargs['filename'] = storage_service
        storage_service = None

    if 'filename' in kwargs and storage_service is None:
        filename = kwargs['filename']
        name, ext = os.path.splitext(filename)
        if ext in ('.hdf', '.h4', '.hdf4', '.he2', '.h5', '.hdf5', '.he5'):
            return _create_storage(HDF5StorageService, trajectory, **kwargs)
        else:
            raise ValueError('Extension `%s` of filename `%s` not understood.' %
                             (ext, filename))

    elif inspect.isclass(storage_service):
        return _create_storage(storage_service, trajectory, **kwargs)
    else:
        return storage_service, set(kwargs.keys())



