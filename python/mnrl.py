# Kevin Angstadt
# angstadt {at} umich.edu
# University of Virginia
#
# Python objects for manipulating MNRL files

import json
import mnrlerror
import jsonschema
import os
from networkx import drawing


def loadMNRL(filename):
    with open(os.path.dirname(os.path.abspath(__file__))+"/mnrl-schema.json", "r") as s:
        schema = json.load(s)
    with open(filename, "r") as f:
        json_string = f.read()

        try:
            jsonschema.validate(json.loads(json_string),schema)
        except jsonschema.exceptions.ValidationError as e:
            print "ERROR:", e
            return None

        # parse into MNRL
        d = MNRLDecoder()
        return d.decode(json_string)

def fromDOT(mnrlName, dotfile):
    """ Generates a MNRL object from a DOT file """

    start, accept, nodes, edges = parseDOT(dotfile)

    # print("Start: ", start)
    # print("Accept: ", accept)
    # print("Nodes: ", nodes)
    # print("Edges: ", edges)

    # Start by making a MNRL network
    mn = MNRLNetwork(mnrlName)

    # Our start nodes are epsilon-transition nodes, so let's make their neighbors start nodes
    real_start_nodes = list()

    # Grab the real start nodes
    for node in start:
        if node in edges.keys():
            for (dst, charset) in edges[node]:
                assert charset == None, "Something's wrong with a start state!: {}".format(charset)
                real_start_nodes.append(dst)

    # Add the nodes
    for src, neighbors in edges.items():

        if src in start:
            continue

        output_ports = []

        # Grab outgoing character sets and put them into our output_ports list
        for (dst, charset) in neighbors:

            if charset not in output_ports:
                output_ports.append((charset, charset))

        # Create a new state for the source with a output_port per neighbor
        state = mn.addState(
            output_ports,
            id=src
        )

        if src in real_start_nodes:
            state.enable = MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN
        
        state.report = src in accept
    
    # Special case where the accept state has no edges
    for node in accept:
        #print("Node ID: ", node)
        if node not in edges.keys():
            state = mn.addState(
                [],
                id=node
            )
        state.report = True
    
    # Now add the edges
    for src, neighbors in edges.items():

        if src in start:
            continue

        for (dst, charset) in neighbors:

            #print("SRC: ", src, "DST: ", dst)

            mn.addConnection((src, charset), (dst, MNRLDefs.STATE_INPUT))
    
    # Now let's make our classical automaton homogeneous!
    homogeneous_mn = make_homogeneous(mn)

    homogeneous_mn.exportToFile(dotfile + '.mnrl')


def make_homogeneous(mn):
    # okay, that's a mnrl definition, but we need to convert it to a
    # homogeneous MNRL
    # This is a copy-paste from Kevin's GIST found here:
    # https://gist.github.com/kevinaangstadt/727252ac84e8c6a15146703ebedd21a3
    
    an = MNRLNetwork("{}_homogeneous".format(mn.id))

    # we're going to rename all the states now, so just keep a count
    num_states = 0

    # each state from the mnrl states can now possibly map to multiple states
    mnrl_states = dict.fromkeys(mn.nodes)
    for k in mnrl_states:
        mnrl_states[k] = dict()

    # add all of the states
    for s in mn.nodes:
        state = mn.getNodeById(s)

        #only add nodes if they have incoming transitions
        for _,(_,src_list) in state.getInputConnections().iteritems():
            # there is only one input, so this happens once
            for src in src_list:
                # we need to create a state with the transition from this port
                # we'll map this to the current state name, but also indicate the input character we match

                # only make a new state if we haven't make one for that input symbol yet
                if src['portId'] not in mnrl_states[s]:
                    mnrl_states[s][src['portId']] = an.addHState(
                        "\\x{0:02x}".format(ord(src['portId'])) if len(src['portId']) == 1 else src['portId'],
                        enable = mn.getNodeById(src['id']).enable,
                        id = "_" + str(num_states),
                        report = state.report
                    )
                    num_states += 1
    # at this point, the states have been made
    # add the transitions
    for s in mn.nodes:
        mn_state = mn.getNodeById(s)

        for port, an_ste in mnrl_states[s].iteritems():
            # for each of these nodes
            # add in the transitions coming into the state from the original
            for _,(_,src_list) in mn_state.getInputConnections().iteritems():
                # there is only one input, so this happens once
                for src in src_list:
                    if src['portId'] == port:
                        # this is the right state for this transition
                        # now, there may be several states actually representing this mnrl state
                        # so we need to make the connection from each
                        for _,src_ste in mnrl_states[src['id']].iteritems():
                            an.addConnection((src_ste.id,MNRLDefs.H_STATE_OUTPUT), (an_ste.id,MNRLDefs.H_STATE_INPUT))

    return an

def parseDOT(filename):
    """ Prase non-homogeneous DOT file and extract data """

    graph = drawing.nx_pydot.read_dot(filename)

    start = []
    accept = []
    nodes = []
    edges = {}

    # Collect nodes
    for node_id, node_info in graph.nodes.items():

        # Found a start node
        if 'START' in node_id:
            start.append(node_id)
        
        # Looking for accept states
        if 'shape' in node_info:

            # Found an accept node!
            if node_info['shape'] == 'doublecircle':
                accept.append(node_id)
        
        nodes.append(node_id)

    for src, neighbors in graph._adj.items():

        for dst, values in neighbors.items():

            # Create a list for the entry; these are the outgoing edges for that
            # src state
            if src not in edges.keys():
                edges[src] = []

            if 'label' in values[0]:

                # Append a tuple to the list
                edges[src].append((dst, values[0]['label'].strip('"')))
            
            # If the edge does not have a label, it's an epsilon transition
            # For non-homogeneous automata, this must mean that the edge
            # comes from a START state
            elif src in start:
                edges[src].append((dst, None))
            
            else:
                raise Exception('We found an edge that is not from a start state, nor does it have a label')

    return start, accept, nodes, edges



class MNRLDefs(object):
    (ENABLE_ON_ACTIVATE_IN,
    ENABLE_ON_START_AND_ACTIVATE_IN,
    ENABLE_ALWAYS,
    ENABLE_ON_LAST,
    TRIGGER_ON_THRESHOLD,
    HIGH_ON_THRESHOLD,
    ROLLOVER_ON_THRESHOLD) = range(7)

    H_STATE_INPUT = STATE_INPUT = "i"
    H_STATE_OUTPUT = UP_COUNTER_OUTPUT = BOOLEAN_OUTPUT = "o"

    UP_COUNTER_COUNT = "cnt"
    UP_COUNTER_RESET = "rst"

    BOOLEAN_TYPES = {
        'and': 1,
        'or': 1,
        'nor': 1,
        'not': 1,
        'nand': 1
    }

    @staticmethod
    def fromMNRLEnable(en):
        if en == "onActivateIn":
            return MNRLDefs.ENABLE_ON_ACTIVATE_IN
        elif en == "onStartAndActivateIn":
            return MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN
        elif en == "onLast":
            return MNRLDefs.ENABLE_ON_LAST
        elif en == "always":
            return MNRLDefs.ENABLE_ALWAYS
        else:
            raise mnrlerror.EnableError(en)

    @staticmethod
    def fromMNRLReportEnable(en):
        if en == "always":
            return MNRLDefs.ENABLE_ALWAYS
        elif en == "onLast":
            return MNRLDefs.ENABLE_ON_LAST
        else:
            raise mnrlerror.ReportEnableError(en)

    @staticmethod
    def toMNRLEnable(en):
        if en == MNRLDefs.ENABLE_ON_ACTIVATE_IN:
            return "onActivateIn"
        elif en == MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN:
            return "onStartAndActivateIn"
        elif en == MNRLDefs.ENABLE_ALWAYS:
            return "always"
        elif en == MNRLDefs.ENABLE_ON_LAST:
            return "onLast"
        else:
            raise mnrlerror.EnableError(en)

    @staticmethod
    def toMNRLReportEnable(en):
        if en == MNRLDefs.ENABLE_ALWAYS:
            return "always"
        elif en == MNRLDefs.ENABLE_ON_LAST:
            return "onLast"
        else:
            raise mnrlerror.ReportEnableError(en)

    @staticmethod
    def fromMNRLCounterMode(m):
        if m == "trigger":
            return MNRLDefs.TRIGGER_ON_THRESHOLD
        elif m == "high":
            return MNRLDefs.HIGH_ON_THRESHOLD
        elif m == "rollover":
            return MNRLDefs.ROLLOVER_ON_THRESHOLD
        else:
            raise mnrlerror.UpCounterModeError(m)

    @staticmethod
    def toMNRLCounterMode(m):
        if m == MNRLDefs.TRIGGER_ON_THRESHOLD:
            return "trigger"
        elif m == MNRLDefs.HIGH_ON_THRESHOLD:
            return "high"
        elif m == MNRLDefs.ROLLOVER_ON_THRESHOLD:
            return "rollover"
        else:
            raise mnrlerror.UpCounterModeError(m)

class MNRLNetwork(object):
    """Represents the top level of a MNRL file."""

    def __init__(self, id):
        """Create a MNRL Network with an id set to 'id'"""
        self.id = id
        self.nodes = dict()
        self._nodes_added = 0

    def toJSON(self):
        return json.dumps({
            'id' : self.id,
            'nodes' : [json.loads(e.toJSON()) for _,e in self.nodes.iteritems()]
        })

    def exportToFile(self, filename):
        """Save the MNRL Network to filename"""
        with open(filename,"w") as f:
            json.dump(json.loads(self.toJSON()), f, indent=2)

    def getNodeById(self, id):
        """Return the element from the MNRL network with the given ID"""
        try:
            return self.nodes[id]
        except KeyError:
            raise mnrlerror.UnknownNode(id)

    def addNode(self,theNode):
        """Add a MNRL Node object to the Network. Note that this may assign an
        ID to the node if none exists."""
        theNode.id = self._getUniqueNodeId(theNode.id)
        self.nodes[theNode.id] = theNode
        return theNode

    def addState(self,
                 outputSymbols,
                 enable = MNRLDefs.ENABLE_ON_ACTIVATE_IN,
                 id = None,
                 report = False,
                 reportEnable = MNRLDefs.ENABLE_ALWAYS,
                 reportId = None,
                 latched = False,
                 attributes = {}
                ):
        """Create a state, add it to the network, and return it"""

        id = self._getUniqueNodeId(id)

        state = State(outputSymbols, enable=enable, id=id, report=report, reportEnable=reportEnable, reportId=reportId, latched=latched, attributes=attributes)

        self.nodes[id] = state

        return state

    def addHState(self,
                  symbols,
                  enable = MNRLDefs.ENABLE_ON_ACTIVATE_IN,
                  id = None,
                  report = False,
                  reportEnable = MNRLDefs.ENABLE_ALWAYS,
                  reportId = None,
                  latched = False,
                  attributes = {}
                 ):
        """Create a homogenous state, add it to the network, and return it"""

        id = self._getUniqueNodeId(id)

        hState = HState(symbols,enable=enable,id=id,report=report,reportEnable=reportEnable,reportId=reportId,latched=latched,attributes=attributes)

        self.nodes[id] = hState

        return hState

    def addUpCounter(self,
                     threshold,
                     mode = MNRLDefs.HIGH_ON_THRESHOLD,
                     id = None,
                     report = False,
                     reportEnable = MNRLDefs.ENABLE_ALWAYS,
                     reportId = None,
                     attributes = {}
                    ):
        """Create an up counter, add it to the network, and return it"""

        id = self._getUniqueNodeId(id)

        new_counter = UpCounter(threshold, mode=mode, id=id, report=report,reportEnable=reportEnable, reportId=reportId, attributes=attributes)

        self.nodes[id] = new_counter

        return new_counter

    def addBoolean(self,
                   booleanType,
                   id = None,
                   report = False,
                   reportEnable = MNRLDefs.ENABLE_ALWAYS,
                   enable = MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN,
                   reportId = None,
                   attributes = {}
                  ):
        """Create a Boolean node, add it to the network, and return it"""
        id = self._getUniqueNodeId(id)

        try:
            number_of_ports = MNRLDefs.BOOLEAN_TYPES[booleanType]
        except KeyError:
            raise mnrlerror.InvalidGateType(booleanType)

        boolean = Boolean(booleanType,portCount=number_of_ports,id=id,enable=enable,report=report,reportEnable=reportEnable,reportId=reportId,attributes=attributes)

        self.nodes[id] = boolean

        return boolean

    def addConnection(self, source, destination):
        """Add a connection between node 'source' (id,port) and 'destination' (id,port)"""
        (s_id,
         s_port,
         s_node,
         s_output_width,
         s_output,
         d_id,
         d_port,
         d_node,
         d_input_width,
         d_input) = self.__getConnectionNodeInformation(source, destination)

        if s_output_width != d_input_width:
            raise mnrlerror.PortWidthMismatch(s_output_width, d_input_width)

        s_output.append({
            'id': d_id,
            'portId': d_port
        })

        d_input.append({
            'id': s_id,
            'portId': s_port
        })

    def removeConnection(self, source, destination):
        """Remove a connection between 'source' (id,port) and 'destination'
        (id,port). If no connection exists, do nothing."""
        (s_id,
         s_port,
         s_node,
         s_output_width,
         s_output,
         d_id,
         d_port,
         d_node,
         d_input_width,
         d_input) = self.__getConnectionNodeInformation(source, destination)

        # remove the connection
        try:
            s_output.remove({
                'id': d_id,
                'portId': d_port
            })
        except ValueError:
            pass # don't care

        try:
            d_input.remove({
                'id': s_id,
                'portId': s_port
            })
        except ValueError:
            pass # don't care

    def _getUniqueNodeId(self,id):
        """return a unique ID for the MNRL network. If an ID is passed in and is
        unique, it will be returned."""
        if id is None:
            id = "_" + str(self._nodes_added)
            self._nodes_added += 1

        if id in self.nodes:
            raise mnrlerror.MNRLDuplicateIdError('This MNRL id already exists: ' + id)

        return id

    def __getConnectionNodeInformation(self, source, destination):
        try:
            s_id, s_port = source
            d_id, d_port = destination
        except ValueError:
            raise mnrlerror.InvalidConnection()

        s_node = self.getNodeById(s_id)
        d_node = self.getNodeById(d_id)

        try:
            s_output_width, s_output = s_node.outputDefs[s_port]
        except KeyError:
            raise mnrlerror.UnknownPort(s_id,s_port)

        try:
            d_input_width, d_input = d_node.inputDefs[d_port]
        except KeyError:
            raise mnrlerror.UnknownPort(d_id,d_port)

        return (s_id,
                s_port,
                s_node,
                s_output_width,
                s_output,
                d_id,
                d_port,
                d_node,
                d_input_width,
                d_input)

class MNRLNode(object):
    def __init__(self,
                 id = None,
                 enable = MNRLDefs.ENABLE_ON_ACTIVATE_IN,
                 report = False,
                 reportEnable = MNRLDefs.ENABLE_ALWAYS,
                 inputDefs = [],
                 outputDefs = [],
                 attributes = {}
                ):
        self.id = id

        if enable not in [
            MNRLDefs.ENABLE_ALWAYS,
            MNRLDefs.ENABLE_ON_ACTIVATE_IN,
            MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN,
            MNRLDefs.ENABLE_ON_LAST
            ]:
            raise mnrlerror.EnableError(enable)
        self.enable = enable

        self.report = report
        
        if reportEnable not in [
            MNRLDefs.ENABLE_ALWAYS,
            MNRLDefs.ENABLE_ON_LAST
        ]:
            raise mnrlerror.ReportEnableError(reportEnable)
        
        self.reportEnable = reportEnable

        #validate input ports
        self.inputDefs = self.__validate_ports(inputDefs,"input")

        #validate output ports
        self.outputDefs = self.__validate_ports(outputDefs,"output")

        self.attributes = attributes

    def toJSON(self):
        # define the enable string
        enable_string = MNRLDefs.toMNRLEnable(self.enable)

        # properly define input ports (drop the connections)
        inputDefs = list()
        for port_id,(width,_) in self.inputDefs.iteritems():
            inputDefs.append({
                'portId': port_id,
                'width': width
            })

        # properly define output ports
        outputDefs = list()
        for port_id,(width,connection_list) in self.outputDefs.iteritems():
            outputDefs.append({
                'portId': port_id,
                'width': width,
                'activate': connection_list
            })
            
        dump_obj = {
            'id' : self.id,
            'report' : self.report,
            'enable' : enable_string,
            'inputDefs' : inputDefs,
            'outputDefs' : outputDefs,
            'attributes' : self.attributes
        }
        
        if self.reportEnable != MNRLDefs.ENABLE_ALWAYS:
            dump_obj['reportEnable'] = MNRLDefs.toMNRLReportEnable(self.reportEnable)

        return json.dumps(dump_obj)

    def getOutputConnections(self):
        """Returns the output connections dict of portid => (width, conn_list)"""
        return self.outputDefs

    def getInputConnections(self):
        """Returns the input connections dict of portid => (width, conn_list)"""
        return self.inputDefs

    def __validate_ports(self,port_def,inout):
        '''Returns a dictionary of ports. Keys are the port id's; each maps to a
        width and list of connections tuple.'''
        portDefs = dict()
        try:
            for port_id,width in port_def:
                # check that the port_id is a string
                if isinstance(port_id, basestring):
                    if port_id in portDefs:
                        raise mnrlerror.DuplicatePortId(port_id)
                    else:
                        if isinstance(width, int):
                            portDefs[port_id] = (width, [])
                        else:
                            raise mnrlerror.InvalidPortWidth(width)
                else:
                    raise mnrlerror.PortIdError(port_id, "the ID is not a string")
        except ValueError:
            raise mnrlerror.PortDefError(inout)
        return portDefs

class State(MNRLNode):
    """A state has one input port and multiple output ports. Output ports are
    enabled by seaparate symbol sets"""
    def __init__(self,
                 outputSymbols,
                 enable = MNRLDefs.ENABLE_ON_ACTIVATE_IN,
                 id = None,
                 report = False,
                 reportEnable = MNRLDefs.ENABLE_ALWAYS,
                 latched = False,
                 reportId = None,
                 attributes = {}
                ):

        symbolSet = dict()

        # outputSymbols is a tuple:
        # ("outputId","symbolSet")
        outputDefs = []
        try:
            for output_id, symbol_set in outputSymbols:
                if isinstance(output_id, basestring):
                    symbolSet[output_id] = symbol_set
                    outputDefs.append((output_id,1))
                else:
                    raise mnrlerror.PortDefError("output")
        except ValueError:
            raise mnrlerror.InvalidStateOutputSymbols()

        super(State,self).__init__(
            id = id,
            enable = enable,
            report = report,
            reportEnable = reportEnable,
            inputDefs = [(MNRLDefs.H_STATE_INPUT,1)],
            outputDefs = outputDefs,
            attributes = attributes
        )

        self.reportId = reportId
        self.latched = latched
        self.outputSymbols = symbolSet

    def toJSON(self):
        j = json.loads(super(State, self).toJSON())
        j.update({'type' : 'state'})
        if self.reportId is not None:
            j['attributes'].update({'reportId':self.reportId})
        j['attributes'].update({
            'latched' : self.latched,
            'symbolSet' : self.outputSymbols
        })
        return json.dumps(j)

class HState(MNRLNode):
    """Object representation of a homogeneous state. A homogenous state only has
    one input port and one output port."""
    def __init__(self,
                  symbols,
                  enable = MNRLDefs.ENABLE_ON_ACTIVATE_IN,
                  id = None,
                  report = False,
                  reportEnable = MNRLDefs.ENABLE_ALWAYS,
                  latched = False,
                  reportId = None,
                  attributes = {}
                ):

        super(HState, self).__init__(
            id = id,
            enable = enable,
            report = report,
            reportEnable = reportEnable,
            inputDefs = [(MNRLDefs.H_STATE_INPUT,1)],
            outputDefs = [(MNRLDefs.H_STATE_OUTPUT,1)],
            attributes = attributes
        )

        self.latched = latched
        self.reportId = reportId
        self.symbols = symbols

    def toJSON(self):
        j = json.loads(super(HState, self).toJSON())
        j.update({'type' : 'hState'})
        if self.reportId is not None:
            j['attributes'].update({'reportId':self.reportId})
        j['attributes'].update({
            'latched' : self.latched,
            'symbolSet' : self.symbols
        })
        return json.dumps(j)

class UpCounter(MNRLNode):
    def __init__(self,
                 threshold,
                 mode = MNRLDefs.HIGH_ON_THRESHOLD,
                 id = None,
                 report = False,
                 reportId = None,
                 attributes = {}
                ):

        #validate that the threshold is a non-negative int
        if not (isinstance(threshold, int) and threshold >= 0):
            raise mnrlerror.UpCounterThresholdError(threshold)

        #validate mode
        if mode not in [
            MNRLDefs.TRIGGER_ON_THRESHOLD,
            MNRLDefs.HIGH_ON_THRESHOLD,
            MNRLDefs.ROLLOVER_ON_THRESHOLD
        ]:
            raise mnrlerror.UpCounterModeError(mode)

        super(UpCounter,self).__init__(
            id = id,
            enable = MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN, #a counter is always active
            report = report,
            reportEnable = reportEnable,
            inputDefs = [
                (MNRLDefs.UP_COUNTER_COUNT, 1),
                (MNRLDefs.UP_COUNTER_RESET, 1)
            ],
            outputDefs = [
                (MNRLDefs.UP_COUNTER_OUTPUT, 1)
            ],
            attributes = attributes
        )

        self.reportId = reportId
        self.threshold = threshold
        self.mode = mode

    def toJSON(self):
        j = json.loads(super(UpCounter, self).toJSON())
        j.update({'type' : 'upCounter'})
        if self.reportId is not None:
            j['attributes'].update({'reportId':self.reportId})
        j['attributes'].update({
            'mode' : MNRLDefs.toMNRLCounterMode(self.mode),
            'threshold' : self.threshold,
        })
        return json.dumps(j)

class Boolean(MNRLNode):
    def __init__(self,
                 gateType,
                 portCount = 1,
                 id = None,
                 enable = MNRLDefs.ENABLE_ON_START_AND_ACTIVATE_IN,
                 report = False,
                 reportEnable = MNRLDefs.ENABLE_ALWAYS,
                 reportId = None,
                 attributes = {}
                ):

        if isinstance(gateType, basestring):
            if not (isinstance(portCount, int) and portCount > 0):
                raise mnrlerror.InvalidGatePortCount(portCount)

            # seems semi-valid, let's create it
            inputDefs = []
            for i in range(portCount):
                inputDefs.append(("b" + str(i),1))

            super(Boolean, self).__init__(
                id = id,
                enable = enable,
                report = report,
                reportEnable = reportEnable,
                inputDefs = inputDefs,
                outputDefs = [(MNRLDefs.BOOLEAN_OUTPUT, 1)],
                attributes = attributes
            )

            self.gateType = gateType
            self.reportId = reportId

        else:
            raise mnrlerror.InvalidGateFormat()
    def toJSON(self):
        j = json.loads(super(Boolean, self).toJSON())
        j.update({'type' : 'boolean'})
        if self.reportId is not None:
            j['attributes'].update({'reportId':self.reportId})
        j['attributes'].update({
            'gateType' : self.gateType,
        })
        return json.dumps(j)

class MNRLDecoder(json.JSONDecoder):
    def decode(self, json_string):
        default_obj = super(MNRLDecoder,self).decode(json_string)

        # build up a proper MNRL representation
        mnrl_obj = MNRLNetwork(default_obj['id'])

        # build up the mnrl network in two passes
        # 1. add all the nodes
        # 2. add all the connections

        for n in default_obj['nodes']:
            # for each node in the network, add it to the network
            if n['type'] == "state":
                node = State(
                    n['attributes']['symbolSet'],
                    enable = MNRLDefs.fromMNRLEnable(n['enable']),
                    id = n['id'],
                    report = n['report'],
                    reportEnable = MNRLDefs.fromMNRLReportEnable(n.get('reportEnable', "always")),
                    latched = n['attributes']['latched'] if 'latched' in n['attributes'] else False,
                    reportId = n['attributes']['reportId'] if 'reportId' in n['attributes'] else None,
                    attributes = n['attributes']
                )
            elif n['type'] == "hState":
                node = HState(
                    n['attributes']['symbolSet'],
                    enable = MNRLDefs.fromMNRLEnable(n['enable']),
                    id = n['id'],
                    report = n['report'],
                    reportEnable = MNRLDefs.fromMNRLReportEnable(n.get('reportEnable', "always")),
                    latched = n['attributes']['latched'] if 'latched' in n['attributes'] else False,
                    reportId = n['attributes']['reportId'] if 'reportId' in n['attributes'] else None,
                    attributes = n['attributes']
                )
            elif n['type'] == "upCounter":
                node = UpCounter(
                    n['attributes']['threshold'],
                    mode = MNRLDefs.fromMNRLCounterMode(n['attributes']['mode']),
                    id = n['id'],
                    report = n['report'],
                    reportEnable = MNRLDefs.fromMNRLReportEnable(n.get('reportEnable', "always")),
                    reportId = n['attributes']['reportId'] if 'reportId' in n['attributes'] else None,
                    attributes = n['attributes']
                )
            elif n['type'] == "Boolean":
                if n['attributes']['gateType'] not in MNRLDefs.BOOLEAN_TYPES:
                    raise mnrlerror.InvalidGateType(n['attributes']['gateType'])
                node = Boolean(
                    n['attributes']['gateType'],
                    portCounte=MNRLDefs.BOOLEAN_TYPES[n['attributes']['gateType']],
                    id = n['id'],
                    enable = MNRLDefs.fromMNRLEnable(n['enable']),
                    report = n['report'],
                    reportEnable = MNRLDefs.fromMNRLReportEnable(n.get('reportEnable', "always")),
                    reportId = n['attributes']['reportId'] if 'reportId' in n['attributes'] else None,
                    attributes = n['attributes']
                )
            else:
                # convert input defs into format needed for constructor
                ins = list()
                for k in n['inputDefs']:
                    ins.append((k['portId'],k['width']))

                # convert output defs into format needed for constructor
                outs = list()
                for k in n['outputDefs']:
                    outs.append((k['portId'], k['width']))

                node = MNRLNode(
                    id = n['id'],
                    enable = MNRLDefs.fromMNRLEnable(n['enable']),
                    report = n['report'],
                    reportEnable = MNRLDefs.fromMNRLReportEnable(n.get('reportEnable', "always")),
                    inputDefs = ins,
                    outputDefs = outs,
                    attributes = n['attributes']
                )

            # add the node to the network
            mnrl_obj.addNode(node)

        for n in default_obj['nodes']:
            # for each node, add all the connections
            for k in n['outputDefs']:
                # for each output port
                for c in k['activate']:
                    mnrl_obj.addConnection(
                        (n['id'],k['portId']),
                        (c['id'],c['portId'])
                    )

        return mnrl_obj
