from graphviz import Digraph
from graphviz import Graph
import yaml
import sys

VERSION = '2019.12.09'

YAML_TAG_CONFIGURATION = 'config'
YAML_TAG_CONFIGURATION_COLORING = 'coloring'
YAML_TAG_STATES_SPECIAL = 'states_special'
YAML_TAG_STATES_TRANSITIONS = 'states_transitions'
YAML_TAG_SECONDARY_STATE_CHECK = 'secondary_state_check'

YAML_TAG_ANYTIME_CALL = 'anytime_call'
YAML_TAG_ANYTIME_REACH = 'anytime_reach'

YAML_TAG_CONFIGURATION_PACKAGENAME = 'package_name'


def path_leaf(path):
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def get_edge_color(fnc, state_model):
    if YAML_TAG_CONFIGURATION_COLORING in state_model[YAML_TAG_CONFIGURATION]:
        if fnc in state_model[YAML_TAG_CONFIGURATION][YAML_TAG_CONFIGURATION_COLORING]:
            return state_model[YAML_TAG_CONFIGURATION][YAML_TAG_CONFIGURATION_COLORING][fnc]

    # if no match found, return default color
    return 'orange'

def generate_graph(state_model_complete, state_model_file, out_folder):
    #
    # standard states and transitions
    #
    state_model = []
    if YAML_TAG_STATES_TRANSITIONS in state_model_complete:
        state_model = state_model_complete[YAML_TAG_STATES_TRANSITIONS]

    dot = Digraph(comment='State model')
    dot.attr('graph', label='Source yaml file: {}'.format(state_model_file), labelloc='t', fontsize='30')
    dot.attr(rankdir='LR', size='8,5')

    # add function transitions
    for start_state in state_model:
        for fnc in state_model[start_state]:
            final_state = state_model[start_state][fnc]
            label = fnc + '()'
            edge_color = get_edge_color(fnc, state_model_complete)
            dot.edge(start_state, final_state, color=edge_color, style='solid', label=label)

    #
    # display special states/transitions
    #
    state_model_special = []
    if YAML_TAG_STATES_SPECIAL in state_model_complete:
        state_model_special = state_model_complete[YAML_TAG_STATES_SPECIAL]

    for start_state in state_model_special:
        if start_state == YAML_TAG_ANYTIME_CALL:
            dot.attr('node', color='green')
            dot.attr('node', style='filled')
            dot.node(start_state)
            for fnc in state_model_special[start_state]:
                label = fnc + '()'
                dot.edge(start_state, start_state, color='orange', style='dotted', label=label)
        if start_state == YAML_TAG_ANYTIME_REACH:
            dot.attr('node', color='green')
            dot.attr('node', style='filled')
            dot.node(start_state)
            for final_state in state_model_special[start_state]:
                dot.attr('node', color='gray')
                dot.attr('node', style='filled')
                dot.edge(start_state, final_state, color='orange', style='dotted')

    # Generate dot graph using GraphViz into pdf
    dot.render('state_model.dot', view=False)


def generate_java_code(state_model_complete, package_name, out_folder):
    state_model = []
    secondary_state_check_model = []
    if YAML_TAG_STATES_TRANSITIONS in state_model_complete:
        state_model = state_model_complete[YAML_TAG_STATES_TRANSITIONS]

    state_model_special = []
    if YAML_TAG_STATES_SPECIAL in state_model_complete:
        state_model_special = state_model_complete[YAML_TAG_STATES_SPECIAL]

    if YAML_TAG_SECONDARY_STATE_CHECK in state_model_complete:
        secondary_state_check_model = state_model_complete[YAML_TAG_SECONDARY_STATE_CHECK]

    #
    # Header
    #

    file_name = '{}StateModel.java'.format(out_folder)

    header = "// Generated by state_enforcer (https://github.com/petrs/state_enforcer) \n"
    header += "package {};\n".format(package_name)
    header += "\n"
    header += "import javacard.framework.ISOException;\n"
    header += "\npublic class StateModel {\n\n"
    header += "    public static final short SW_FUNCTINNOTALLOWED                      = (short) 0x9AF0;\n" \
              "    public static final short SW_UNKNOWNSTATE                           = (short) 0x9AF1;\n" \
              "    public static final short SW_UNKNOWNFUNCTION                        = (short) 0x9AF2;\n" \
              "    public static final short SW_INCORRECTSTATETRANSITION               = (short) 0x9AF3;\n\n\n" \
              "    // States constants\n" \
              "    public static final short STATE_UNSPECIFIED                         = (short) 0xF0F0;\n"

    with open(file_name, "w") as file:
        file.write(header)

        indent = "    "
        padding_indent_len = 72

        #
        # Generate state and function constants
        #
        # Extract all states and sort
        all_states = []
        for state_name in state_model:
            if state_name not in all_states:
                all_states.append(state_name)

        if YAML_TAG_ANYTIME_REACH in state_model_special:
            anytime_allowed = state_model_special[YAML_TAG_ANYTIME_REACH]
            for state_name in anytime_allowed:
                if state_name not in all_states:
                    all_states.append(state_name)

        # include also secondary models check
        for state_name in secondary_state_check_model:
            if state_name not in all_states:
                all_states.append(state_name)

        all_states.sort()

        MAX_SHORT = 32768
        const_step = round(MAX_SHORT / (len(all_states) + 1))
        const_index = const_step
        print("INFO: {} unique states found:".format(len(all_states)))
        for state_name in all_states:
            # constant for current state
            message = "    public static final short {}".format(state_name)
            remaining_padd = padding_indent_len - len(message)
            while remaining_padd > 0:
                message += " "
                remaining_padd -= 1

            message += "= (short) 0x{:04X}; // {}\n".format(const_index, f"{const_index:016b}")
            file.write(message)
            const_index += const_step

            print(state_name)

        # Extract all functions and sort
        sorted_unique_fncs = []
        for state_name in state_model:
            for fnc in state_model[state_name]:
                if fnc not in sorted_unique_fncs:
                    sorted_unique_fncs.append(fnc)
        if YAML_TAG_ANYTIME_CALL in state_model_special:
            anytime_allowed = state_model_special[YAML_TAG_ANYTIME_CALL]
            for fnc_name in anytime_allowed:
                if fnc_name not in sorted_unique_fncs:
                    sorted_unique_fncs.append(fnc_name)
        for state_name in secondary_state_check_model:
            for fnc in secondary_state_check_model[state_name]:
                if fnc not in sorted_unique_fncs:
                    sorted_unique_fncs.append(fnc)
        sorted_unique_fncs.sort()

        const_step = round(MAX_SHORT / (len(sorted_unique_fncs) + 1))
        const_index = const_step
        #const_index = 1 + 0x4000 # function constants prefix
        print("\nINFO: {} unique functions found:".format(len(sorted_unique_fncs)))
        file.write("\n    // Functions constants\n")
        for fnc in sorted_unique_fncs:
            # constant for functions state
            if len(fnc) > 0:
                message = "    public static final short FNC_{}".format(fnc)
                remaining_padd = padding_indent_len - len(message)
                while remaining_padd > 0:
                    message += " "
                    remaining_padd -= 1

                message += "= (short) 0x{:04X}; // {}\n".format(const_index, f"{const_index:016b}")
                file.write(message)
                const_index += const_step

                print(fnc)

        print('\n\n')

        value = "\n\n    private short STATE_CURRENT = STATE_UNSPECIFIED;\n\n" \
                + "    private short STATE_SECONDARY = STATE_UNSPECIFIED;\n\n" \
                + "" \
                + "    public StateModel(short startState) {\n" \
                + "        STATE_CURRENT = startState;\n" \
                + "    }\n" \
                + "    \n" \
                + "    public void checkAllowedFunction(short requestedFnc) {\n" \
                + "        // Check allowed function in current state\n" \
                + "        checkAllowedFunction(requestedFnc, STATE_CURRENT);\n" \
                + "        // // Check secondary state (if required)\n" \
                + "        checkAllowedFunctionSecondary(requestedFnc, STATE_SECONDARY);\n" \
                + "    }\n" \
                + "    \n" \
                + "    public short changeState(short newState) {\n" \
                + "        STATE_CURRENT = changeState(STATE_CURRENT, newState);\n" \
                + "        return STATE_CURRENT;\n" \
                + "    }\n" \
                + "    public short setSecondaryState(short newSecondaryState) {\n" \
                + "        STATE_SECONDARY = newSecondaryState;\n" \
                + "        return STATE_SECONDARY;\n" \
                + "    }\n" \
                + "    \n" \
                + "    public short getState() {\n" \
                + "        return STATE_CURRENT;\n" \
                + "    }\n\n"
        file.write(value)

        #
        # CheckAllowedFunction
        value = "    private static void checkAllowedFunction(short requestedFnc, short currentState) {\n"
        value += "        // Check for functions which can be called from any state\n" \
                 + "        switch (requestedFnc) {\n" \
                 + "            // case FNC_someFunction:  return;    // enable if FNC_someFunction can be called from any state (typical for cleaning instructions)\n"

        anytime_allowed = []
        if YAML_TAG_ANYTIME_CALL in state_model_special:
            anytime_allowed = state_model_special[YAML_TAG_ANYTIME_CALL]

        for fnc in sorted(anytime_allowed):
            value += "            case FNC_{}:  return;\n".format(fnc)

        value += "        }\n\n"
        file.write(value)

        value = "        // Check if function can be called from current state\n" \
                + "        switch (currentState) {\n"
        file.write(value)

        # Allowed functions in a given state
        for state in sorted(state_model.keys()):
            # case for current state
            message = "            case {}:\n".format(state)
            file.write(message)

            fncs_set = set(state_model[state])
            sorted_fncs = sorted(fncs_set)
            for function in sorted_fncs:
                if len(function) > 0:
                    message = "{}{}{}{}if (requestedFnc == FNC_{}) return;\n".format(indent, indent, indent, indent, function)
                    file.write(message)

            # end current case
            message = "                ISOException.throwIt(SW_FUNCTINNOTALLOWED); // if reached, function is not allowed in given state\n" \
                      + "                break;\n" \
                      + ""
            file.write(message)

        value = "            default:\n" \
                + "                ISOException.throwIt(SW_UNKNOWNSTATE);\n" \
                + "                break;\n" \
                + "       }\n" \
                + "    }\n\n"

        file.write(value)







        #
        # checkAllowedFunctionSecondary
        value = "    private static void checkAllowedFunctionSecondary(short requestedFnc, short currentSecondaryState) {\n"
        value += "        // Check for functions which can be called from any state\n" \
                 + "        switch (requestedFnc) {\n" \
                 + "            // case FNC_someFunction:  return;    // enable if FNC_someFunction can be called from any state (typical for cleaning instructions)\n"

        anytime_allowed = []
        if YAML_TAG_ANYTIME_CALL in state_model_special:
            anytime_allowed = state_model_special[YAML_TAG_ANYTIME_CALL]

        for fnc in sorted(anytime_allowed):
            value += "            case FNC_{}:  return;\n".format(fnc)

        value += "        }\n\n"
        file.write(value)

        value = "        // Check if function can be called from current state\n" \
                + "        switch (currentSecondaryState) {\n"
        file.write(value)

        # Allowed functions in a given state
        for state in sorted(secondary_state_check_model.keys()):
            # case for current state
            message = "            case {}:\n".format(state)
            file.write(message)

            fncs_set = set(secondary_state_check_model[state])
            sorted_fncs = sorted(fncs_set)
            for function in sorted_fncs:
                if len(function) > 0:
                    message = "{}{}{}{}if (requestedFnc == FNC_{}) return;\n".format(indent, indent, indent, indent, function)
                    file.write(message)

            # end current case
            message = "                ISOException.throwIt(SW_FUNCTINNOTALLOWED); // if reached, function is not allowed in given state\n" \
                      + "                break;\n" \
                      + ""
            file.write(message)

        value = "            default:\n" \
                + "                ISOException.throwIt(SW_UNKNOWNSTATE);\n" \
                + "                break;\n" \
                + "       }\n" \
                + "    }\n\n"

        file.write(value)








        #
        # Allowed state transitions in a given state
        value = "    private static short changeState(short currentState, short newState) {\n"
        value += "        // Check for states which can be reached from any other state (typically some \"cleaning\" state)\n" \
                 + "        switch (newState) {\n" \
                 + "            //case STATE_ALWAYS_REACHABLE: return newState;\n"

        anytime_allowed = []
        if YAML_TAG_ANYTIME_REACH in state_model_special:
            anytime_allowed = state_model_special[YAML_TAG_ANYTIME_REACH]
        for state in sorted(anytime_allowed):
            value += "            case {}: return newState;\n".format(state)

        value += "        }\n\n"

        file.write(value)

        value = "        switch (currentState) {\n"
        file.write(value)

        for state in sorted(state_model.keys()):
            # case for current state
            message = "            case {}:\n".format(state)
            file.write(message)

            fncs_set = set(state_model[state])
            sorted_fncs = sorted(fncs_set)
            sorted_states = []
            for fnc in sorted_fncs:
                if state_model[state][fnc] not in sorted_states:
                    sorted_states.append(state_model[state][fnc])

            sorted_states.sort()

            for target_state in sorted_states:
                message = "{}{}{}{}if (newState == {}) return newState;\n".format(indent, indent, indent, indent, target_state)
                file.write(message)

            # end current case
            message = "                ISOException.throwIt(SW_INCORRECTSTATETRANSITION); // if reached, transition is not allowed\n" \
                      + "                break;\n" \
                      + ""
            file.write(message)

        value = "            default:\n" \
                + "                ISOException.throwIt(SW_UNKNOWNSTATE);\n" \
                + "                break;\n" \
                + "       }\n" \
                + "       ISOException.throwIt(SW_INCORRECTSTATETRANSITION); // if reached, transition is not allowed\n" \
                + "       return newState;\n" \
                + "    }\n\n"

        file.write(value)

        #
        # Footer
        footer = "}\n"
        file.write(footer)

    return


def print_help():
    print('state_enforcer, version ' + VERSION)
    print('Petr Svenda, 2019')
    print('Reads state transition model from yaml file, generates .dot visualization and Java enforcement methods \n' 
            'checking allowed state transitions and allowed function calls for the current state.')
    print('See https://github.com/petrs/state_enforcer for more details.')
    print('\nUsage:')
    print('   state_enforcer.py path_to_yaml_file_with_state_model.yml')


def render_state_model():
    if len(sys.argv) < 2:
        print_help()
        return

    # state_file = 'state_model.yml'
    package_name = 'yourpackage'

    # first argument is always required
    state_file = sys.argv[1]

    out_folder = ''
    if len(sys.argv) > 2:
        out_folder = sys.argv[2]
        if out_folder[len(out_folder) - 1] != '\\':
            out_folder += '\\'

    # load states from yaml
    with open(state_file) as file:
        state_model = yaml.load(file, Loader=yaml.FullLoader)
        # print(state_model)

    if YAML_TAG_CONFIGURATION in state_model:
        if YAML_TAG_CONFIGURATION_PACKAGENAME in state_model[YAML_TAG_CONFIGURATION]:
            package_name = state_model[YAML_TAG_CONFIGURATION][YAML_TAG_CONFIGURATION_PACKAGENAME]

    generate_java_code(state_model, package_name, out_folder)
    generate_graph(state_model, state_file, out_folder)


def main():
    render_state_model()


if __name__ == "__main__":
    main()
