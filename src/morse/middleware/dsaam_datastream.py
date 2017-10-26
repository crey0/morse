"""The DSAAMROS 'datastream manager' is responsible for DSAAM/ROS topic
management in MORSE. It can currently only be used in FixedSimulationStep
strategy, as it expects an exact simulation step and enforces time
synchronisation with subscribed topics. In particulare the action() method is
blocking until all messages up to the current time have arrived and been
delivered.

It expects to be used with ROS middleware datastreams (e.g. implementing
morse.middleware.ros.abstract_ros.ROSPublisher or
morse.middleware.ros.abstract_ros.ROSSubscriber) and automatically encapsulates
datastream for usage with the DSAAM/ROS library.

"""
import logging; logger = logging.getLogger("morse." + __name__)
from morse.core.datastream import DatastreamManager
from dsaam.ros.ros_node import RosNode, Time
from dsaam.time import NS_IN_SECOND
from morse.middleware.ros.abstract_ros import ROSPublisher, ROSSubscriber, Header
import importlib
import sys
from morse.core import blenderapi

def get_class(classpath):
    """Get class from classpath, using importlib. Will throw if class or path
    doesn't exist.

    """
    m_name, c_name = classpath.rsplit('.', maxsplit=1)
    module = importlib.import_module(m_name)
    m_class = getattr(module, c_name)
    return m_class

def datastream_initialize(self):
    """This is the initialize() method of the DSAAM datastream proxy created
    automatically by DSAAMROSDatastreamManager.register_component(), overriding
    the default one.  

    Depending of the base class, initializes proper subscriber or publisher in
    their DSAAM node.

    """
    # Calling base class initializer
    self.__class__.__base__.initialize(self)

    # TODO proper dt and sinks
    freq = self.component_instance.frequency
    queue_size = ROSPublisher.determine_queue_size(self)
    period = int(NS_IN_SECOND//freq)
    dt = Time(nanos=period)

    start_time = self.kwargs.get("start_time", self.dsaam_node.time)
    
    # setting up pub/sub
    if issubclass(self.__class__, ROSPublisher):
        sinks = self.kwargs.get("subscribers", None)
        logger.info("Setting subs for pub {} : {}".format(self.topic_name, sinks)) 
        self.dsaam_node.setup_publisher(self.topic_name, self.ros_class_orig,
                                        start_time, dt,
                                        queue_size,
                                        sinks=sinks)
        
    if issubclass(self.__class__, ROSSubscriber):
        self.dsaam_node.setup_subscriber(self.topic_name, self.ros_class_orig,
                                         self.dsaam_callback,
                                         start_time, dt,
                                         queue_size)

def dsaam_callback(self, topic, message, tmin_next):
    """This is the callback() method of the DSAAM datastream proxy created
    automatically by DSAAMROSDatastreamManager.register_component(), overriding
    the default one.

    """
    m, t, dt = message
    self.callback(m)
    
def dsaam_publish(self, m):
    """This is the callback() method of the DSAAM datastream proxy created
    automatically by DSAAMROSDatastreamManager.register_component(), overriding
    the default one.

    Publishes the data on rostopic via DSAAM node

    """
    m_time =  Time(m.header.stamp.secs, m.header.stamp.nsecs)

    # Ugly hack to account for the fact that morse time is in float, and
    # therefore subject to rounding error.
    # TODO find better solution
    if m_time != self.dsaam_node.time:
        logger.warning("Time discrepancy when publishing message, expected {} "
                       "got {}. Resetting message time "\
                       .format(self.dsaam_node.time, m_time))
        m_time(self.dsaam_node.time)
                    
    self.dsaam_node.send(self.topic_name, m, m_time)
    self.sequence +=1
    logger.warning("{} : publishing message {}:{} ".format(self.topic_name, self.sequence, m_time))

# This module
module = sys.modules[__name__]

class DSAAMROSDatastreamManager(DatastreamManager):
    """Handle communication between Blender and DSAAM/ROS."""
    
    def __init__(self, args, kwargs):
        # Call the constructor of the parent class
        DatastreamManager.__init__(self, args, kwargs)
        
        start_time = Time(\
            nanos=int(NS_IN_SECOND * blenderapi.persistantstorage().time.time))
        dt = Time(nanos=int(NS_IN_SECOND//blenderapi.getfrequency()))
        start_time += dt #TODO cleanup this hack
        logger.warning("Setting up DSAAM node with time={}, dt={}"\
                       .format(start_time,dt))

        default_qsize = 0 # This means that ALL datastreams must setup
                          # appropriate queue sizes

        # Creating DSAAM node.
        self.node = RosNode("morse", start_time, dt, default_qsize)
        self.init_done = False

    def finalize(self):
        DatastreamManager.finalize(self)
        # TODO : implement proper finalize when available in DSAAM/ROS
        del node

    def register_component(self, component_name, component_instance, mw_data):
        # Get the ROS datastream class
        klass = get_class(mw_data[1])
        klass_name = klass.__name__

        # Create derived class for DSAAM encapsulation, if it doesn't exist
        proxy_name = "DSAAM"+klass_name
        if proxy_name not in module.__dict__:
            proxy_class = type(proxy_name, (klass,),
                               {'ros_class':Header,
                                'ros_class_orig':klass.ros_class,
                                'dsaam_node':self.node,
                                'dsaam_callback':dsaam_callback,
                                'publish': dsaam_publish,
                                'initialize': datastream_initialize})
        
            #Set newly created class as module attribute to be found later
            module.__setattr__(proxy_class.__name__, proxy_class)

        # Set classpath datatastream to the proxy 
        mw_data[1]='morse.middleware.dsaam_datastream.' + proxy_class.__name__

        # Register the component = create the datastream
        DatastreamManager.register_component(self, component_name,
                                             component_instance, mw_data)
        

    def action(self):
        logger.warning("--> action()")

        node=self.node
        
        next_time = node.time + node.dt

        # Init can only be called once all subscribers and publishers have been
        # setup, therefore it is called here, which is suboptimal.
        if not self.init_done:
            node.ros_init(init_node=False)
            node.init()
            self.init_done = True
            logger.warning("action() ROS init OK")

        else:
            # If this is not the first call, step to the next time related to
            # ugly hack start_time = start_time + dt in __init__
            node.step(next_time)

        # Delivering all messages up to time + dt
        while node.next_time() < next_time:
            node.next()

        logger.warning("action() : Stepping to {}".format(next_time))
        logger.warning("<-- action()".format(next_time))



