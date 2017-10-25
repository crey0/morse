DSAAM
========

The `DSAAM` library adds time management capabilities to message passing
middlewares. Currently, only the ROS middleware is supported, as well as
communication in the same process via threads.

The library is currently in development, in an alpha stage.

The DSAAM/ROS API is availabe for Python>=3 and C++>=11.

Files
-----

- Python: ``$MORSE_ROOT/src/morse/middleware/dsaam_datastream.py``

.. _dsaam_ds_configuration:

Configuration specificities
---------------------------

Still in alpha stage.

.. code-block :: python

    foo.add_stream('dsaam/ros', 'morse.middleware.ros.my_datastream.MyDatastream')


