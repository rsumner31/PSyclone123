# -----------------------------------------------------------------------------
# (c) The copyright relating to this work is owned by the Science,
# Technology and Facilities Council, 2016.
# -----------------------------------------------------------------------------
# Author A. R. Porter, STFC Daresbury Lab
# Modified I. Kavcic, Met Office

''' This module implements the support for 'built-in' operations in the
    PSyclone Dynamo 0.3 API. Each supported built-in is implemented as
    a different Python class, all inheriting from the DynBuiltIn class.
    The DynBuiltInCallFactory creates the Python object required for
    a given built-in call. '''

import psyGen
from psyGen import BuiltIn, NameSpaceFactory
from parse import ParseError
from dynamo0p3 import DynLoop, DynKernelArguments

# The name of the file containing the meta-data describing the
# built-in operations for this API
BUILTIN_DEFINITIONS_FILE = "dynamo0p3_builtins_mod.f90"
# overide the default reduction operator mapping. This is used for
# reproducible reductions.
psyGen.REDUCTION_OPERATOR_MAPPING = {"gh_sum": "+"}
# The types of argument that are valid for built-in kernels in the
# Dynamo 0.3 API
VALID_BUILTIN_ARG_TYPES = ["gh_field", "gh_real"]


# Function to return the built-in operations that we support for this API. 
# The meta-data describing these kernels is in dynamo0p3_builtins_mod.f90. 
# The built-in operations F90 names are dictionary keys and need to be 
# converted to lower case for invoke generation purpose.
def get_builtin_map(BUILTIN_MAP_F90):
    '''Convert the names of the supported built-in operations to lowercase
    for comparison and invoke generation purpose'''

    BUILTIN_MAP = {}
    for fortran_name in BUILTIN_MAP_F90:
        python_name = BUILTIN_MAP_F90[fortran_name]
        BUILTIN_MAP[fortran_name.lower()] = python_name
    return BUILTIN_MAP


class DynBuiltInCallFactory(object):
    ''' Creates the necessary framework for a call to a Dynamo built-in,
    This consists of the operation itself and the loop over unique DoFs. '''

    def __str__(self):
        return "Factory for a call to a Dynamo built-in"

    @staticmethod
    def create(call, parent=None):
        ''' Create the objects needed for a call to the built-in
        described in the call (BuiltInCall) object '''

        if call.func_name not in BUILTIN_MAP:
            raise ParseError(
                "Unrecognised built-in call. Found '{0}' but expected "
                "one of '{1}'".format(call.func_name,
                                      BUILTIN_MAP_F90.keys()))

        # Use our dictionary to get the correct Python object for
        # this built-in.
        builtin = BUILTIN_MAP[call.func_name]()

        # Create the loop over DoFs
        dofloop = DynLoop(parent=parent,
                          loop_type="dofs")

        # Use the call object (created by the parser) to set-up the state
        # of the infrastructure kernel
        builtin.load(call, parent=dofloop)

        # Check that our assumption that we're looping over DoFS is valid
        if builtin.iterates_over != "dofs":
            raise NotImplementedError(
                "In the Dynamo 0.3 API built-in calls must iterate over "
                "DoFs but found {0} for {1}".format(builtin.iterates_over,
                                                    str(builtin)))
        # Set-up its state
        dofloop.load(builtin)
        # As it is the innermost loop it has the kernel as a child
        dofloop.addchild(builtin)

        # Return the outermost loop
        return dofloop


class DynBuiltIn(BuiltIn):
    ''' Parent class for a call to a Dynamo Built-in. '''

    def __str__(self):
        raise NotImplementedError("DynBuiltIn.__str__ must be overridden")

    def __init__(self):
        self._name_space_manager = NameSpaceFactory().create()
        # Look=up/create the name of the loop variable for the loop over DoFs
        self._idx_name = self._name_space_manager.\
            create_name(root_name="df",
                        context="PSyVars",
                        label="dof_loop_idx")
        BuiltIn.__init__(self)

    def load(self, call, parent=None):
        ''' Populate the state of this object using the supplied call
        object. '''
        from dynamo0p3 import FSDescriptors
        BuiltIn.load(self, call, DynKernelArguments(call, self), parent)
        self.arg_descriptors = call.ktype.arg_descriptors
        self._func_descriptors = call.ktype.func_descriptors
        self._fs_descriptors = FSDescriptors(call.ktype.func_descriptors)
        # Check that this built-in kernel is valid
        self._validate()

    def _validate(self):
        ''' Check that this built-in conforms to the Dynamo 0.3 API '''
        write_count = 0  # Only one argument must be written to
        field_count = 0  # We must have one or more fields as arguments
        spaces = set()   # All field arguments must be on the same space
        for arg in self.arg_descriptors:
            if arg.access in ["gh_write", "gh_sum", "gh_inc"]:
                write_count += 1
            if arg.type == "gh_field":
                field_count += 1
                spaces.add(arg.function_space)
            if arg.type not in VALID_BUILTIN_ARG_TYPES:
                raise ParseError(
                    "In the Dynamo 0.3 API an argument to a built-in kernel "
                    "must be one of {0} but kernel {1} has an argument of "
                    "type {2}".format(VALID_BUILTIN_ARG_TYPES, self.name,
                                      arg.type))
        if write_count != 1:
            raise ParseError("A built-in kernel in the Dynamo 0.3 API must "
                             "have one and only one argument that is written "
                             "to but found {0} for kernel {1}".
                             format(write_count, self.name))
        if field_count == 0:
            raise ParseError("A built-in kernel in the Dynamo 0.3 API "
                             "must have at least one field as an argument but "
                             "kernel {0} has none.".format(self.name))
        if len(spaces) != 1:
            raise ParseError(
                "All field arguments to a built-in in the Dynamo 0.3 API "
                "must be on the same space. However, found spaces {0} for "
                "arguments to {1}".format([x for x in spaces], self.name))

    def array_ref(self, fld_name):
        ''' Returns a string containing the array reference for a
        proxy with the supplied name '''
        return fld_name + "%data(" + self._idx_name + ")"

    @property
    def undf_name(self):
        ''' Dynamically looks up the name of the undf variable for the
        space that this kernel updates '''
        field = self._arguments.iteration_space_arg()
        from dynamo0p3 import get_fs_undf_name
        return get_fs_undf_name(field.function_space)

    @property
    def qr_required(self):
        ''' Built-ins do not currently require quadrature '''
        return False

    def gen_code(self, parent):
        raise NotImplementedError("DynBuiltIn.gen_code must be overridden")

    def cma_operation(self):
        ''' Built-ins do not perform operations with Column-Matrix-Assembly
        operators '''
        return None
#---------------------------------------------------------------------#
#=============== Adding (scaled) fields ==============================#
#---------------------------------------------------------------------#
class DynXPlusYKern(DynBuiltIn):
    ''' Add one field to another and return the result as a third field '''

    def __str__(self):
        return "Built-in: Add fields"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We add each element of f2 to the corresponding element of f1
        # and store the result in f3.
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name3,
                             rhs=field_name1 + " + " + field_name2))


class DynIncXPlusYKern(DynBuiltIn):
    ''' Add the 2nd field to the first field and return it '''

    def __str__(self):
        return "Built-in: Increment field"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We add each element of f1 to the corresponding element of f2
        # and store the result back in f1.
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[1].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name1,
                             rhs=field_name1 + " + " + field_name2))


class DynAXPlusYKern(DynBuiltIn):
    ''' f = a.x + y where 'a' is a scalar and 'f', 'x' and
    'y' are fields '''

    def __str__(self):
        return "Built-in: aX_plus_Y"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f1 (3rd arg) by a scalar
        # (2nd arg), add it to the corresponding
        # element of a second field (4th arg)  and write the value to the
        # corresponding element of field f3 (1st arg).
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        scalar_name = self._arguments.args[1].name
        field_name1 = self.array_ref(self._arguments.args[2].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[3].proxy_name)
        rhs_expr = scalar_name + "*" + field_name1 + " + " + field_name2
        parent.add(AssignGen(parent, lhs=field_name3, rhs=rhs_expr))


class DynIncAXPlusYKern(DynBuiltIn):
    ''' x = a.x + y where 'a' is a scalar and 'x' and 'y' are fields '''

    def __str__(self):
        return "Built-in: inc_aX_plus_Y"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f1 (2nd arg) by a scalar
        # (1st arg), add it to the corresponding element of a
        # second field (3rd arg) and write the value back into
        # the element of field f1.
        scalar_name = self._arguments.args[0].name
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        rhs_expr = scalar_name + "*" + field_name1 + " + " + field_name2
        parent.add(AssignGen(parent, lhs=field_name1, rhs=rhs_expr))


class DynIncXPlusBYKern(DynBuiltIn):
    ''' x = x + b.y where 'b' is a scalar and 'x' and 'y' are
    fields '''

    def __str__(self):
        return "Built-in: inc_X_plus_bY"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f2 (3rd arg) by a scalar (2nd arg),
        # add it to the corresponding element of a first field f1 (1st arg)
        # and write the value back into the element of field f1.
        scalar_name = self._arguments.args[1].name
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        rhs_expr = field_name1 + " + " + scalar_name + "*" + field_name2
        parent.add(AssignGen(parent, lhs=field_name1, rhs=rhs_expr))


class DynAXPlusBYKern(DynBuiltIn):
    ''' f = a.x + b.y where 'a' and 'b' are scalars and 'f', 'x' and
    'y' are fields '''

    def __str__(self):
        return "Built-in: aX_plus_bY"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f1 (3rd arg) by the first
        # scalar (2nd arg), add it to the product of the corresponding
        # element of a second field (5th arg) with the second scalar
        # (4th arg) and write the value to the corresponding element
        # of field f3 (1st arg).
        field_name3  = self.array_ref(self._arguments.args[0].proxy_name)
        scalar_name1 = self._arguments.args[1].name
        scalar_name2 = self._arguments.args[3].name
        field_name1  = self.array_ref(self._arguments.args[2].proxy_name)
        field_name2  = self.array_ref(self._arguments.args[4].proxy_name)
        rhs_expr = (scalar_name1 + "*" + field_name1 + " + " +
                    scalar_name2 + "*" + field_name2)
        parent.add(AssignGen(parent, lhs=field_name3, rhs=rhs_expr))


class DynIncAXPlusBYKern(DynBuiltIn):
    ''' x = a.x + b.y where 'a' and 'b' are scalars and 'x' and 'y' are
    fields '''

    def __str__(self):
        return "Built-in: inc_aX_plus_bY"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f1 (2nd arg) by the first scalar
        # (1st arg), add it to the product of the corresponding element of
        # a second field (4th arg) with the second scalar (4rd arg) and
        # write the value back into the element of field f1.
        scalar_name1 = self._arguments.args[0].name
        scalar_name2 = self._arguments.args[2].name
        field_name1  = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2  = self.array_ref(self._arguments.args[3].proxy_name)
        rhs_expr = (scalar_name1 + "*" + field_name1 + " + " +
                    scalar_name2 + "*" + field_name2)
        parent.add(AssignGen(parent, lhs=field_name1, rhs=rhs_expr))
#---------------------------------------------------------------------#
#=============== Subtracting (scaled) fields =========================#
#---------------------------------------------------------------------#
class DynXMinusYKern(DynBuiltIn):
    ''' Subtract one field from another and return the result as a
    third field '''

    def __str__(self):
        return "Built-in: Subtract fields"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We subtract each element of f2 from the corresponding element
        # of f1 and store the result in f3.
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        assign = AssignGen(parent, lhs=field_name3,
                           rhs=field_name1 + " - " + field_name2)
        parent.add(assign)


class DynAXMinusYKern(DynBuiltIn):
    ''' f = a.x - y where 'a' is a scalar and 'f', 'x' and
    'y' are fields '''

    def __str__(self):
        return "Built-in: aX_minus_Y"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f1 (3rd arg) by a scalar
        # (2nd arg), subtract it from the corresponding
        # element of a second field (4th arg)  and write the value to the
        # corresponding element of field f3 (1st arg).
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        scalar_name = self._arguments.args[1].name
        field_name1 = self.array_ref(self._arguments.args[2].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[3].proxy_name)
        rhs_expr = scalar_name + "*" + field_name1 + " - " + field_name2
        parent.add(AssignGen(parent, lhs=field_name3, rhs=rhs_expr))


class DynIncXMinusBYKern(DynBuiltIn):
    ''' x = x - b.y where 'b' is a scalar and 'x' and 'y' are
    fields '''

    def __str__(self):
        return "Built-in: inc_X_minus_bY"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply one element of field f2 (3rd arg) by a scalar (2nd arg),
        # subtract it fom  the corresponding element of a first field f1
        # (1st arg) and write the value back into the element of field f1.
        scalar_name = self._arguments.args[1].name
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        rhs_expr = field_name1 + " - " + scalar_name + "*" + field_name2
        parent.add(AssignGen(parent, lhs=field_name1, rhs=rhs_expr))
#---------------------------------------------------------------------#
#=============== Multiplying (scaled) fields =========================#
#---------------------------------------------------------------------#
class DynXTimesYKern(DynBuiltIn):
    ''' DoF-wise product of one field with another with the result
    returned as a third field '''

    def __str__(self):
        return "Built-in: Multiply fields"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We subtract each element of f2 from the corresponding element
        # of f1 and store the result in f3.
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        assign = AssignGen(parent, lhs=field_name3,
                           rhs=field_name1 + " * " + field_name2)
        parent.add(assign)


class DynIncXTimesYKern(DynBuiltIn):
    ''' Multiply the first field by the second and return it '''

    def __str__(self):
        return "Built-in: Multiply field by another"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply each element of f1 by the corresponding element of
        # f2 and store the result back in f1.
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[1].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name1,
                             rhs=field_name1 + " * " + field_name2))
#---------------------------------------------------------------------#
#=============== Scaling fields ======================================#
#---------------------------------------------------------------------#
class DynATimesXKern(DynBuiltIn):
    ''' Multiply the first field by a scalar and return the result as
    a second field (y = a*x) '''

    def __str__(self):
        return "Built-in: Copy scaled field"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We multiply each element of f1 by the scalar argument and
        # store the result in f2.
        field_name2 = self.array_ref(self._arguments.args[0].proxy_name)
        scalar_name = self._arguments.args[1].name
        field_name1 = self.array_ref(self._arguments.args[2].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name2,
                             rhs=scalar_name + " * " + field_name1))


class DynIncATimesXKern(DynBuiltIn):
    ''' Multiply a field by a scalar and return it '''

    def __str__(self):
        return "Built-in: Scale a field"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # In this case we're multiplying each element of a field by the
        # supplied scalar value.
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        scalar_name = self._arguments.args[0].name
        parent.add(AssignGen(parent, lhs=field_name1,
                             rhs=scalar_name + "*" + field_name1))
#---------------------------------------------------------------------#
#=============== Dividing (scaled) fields ============================#
#---------------------------------------------------------------------#
class DynXDividebyYKern(DynBuiltIn):
    ''' Divide the first field by the second and return the result as
    a third field '''

    def __str__(self):
        return "Built-in: Divide fields"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We divide each element of f1 by the corresponding element of
        # f2 and store the result in f3.
        field_name3 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[2].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name3,
                             rhs=field_name1 + " / " + field_name2))


class DynIncXDividebyYKern(DynBuiltIn):
    ''' Divide the first field by the second and return it '''

    def __str__(self):
        return "Built-in: Divide one field by another"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We divide each element of f1 by the corresponding element of
        # f2 and store the result back in f1.
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name2 = self.array_ref(self._arguments.args[1].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name1,
                             rhs=field_name1 + " / " + field_name2))
#---------------------------------------------------------------------#
#=============== Raising field to a scalar ===========================#
#---------------------------------------------------------------------#
class DynIncXPowrealAKern(DynBuiltIn):
    ''' Raise a field to an exponent and return it '''

    def __str__(self):
        return "Built-in: raise a field to a real exponent"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # In this case we're raising each element of a field to a
        # supplied scalar value.
        field_name1 = self.array_ref(self._arguments.args[0].proxy_name)
        real_power  = self._arguments.args[1].name
        parent.add(AssignGen(parent, lhs=field_name1,
                             rhs=field_name1 + "**" + real_power))
#---------------------------------------------------------------------#
#=============== Setting field elements to a value  ==================#
#---------------------------------------------------------------------#
class DynSetvalCKern(DynBuiltIn):
    ''' Set a field equal to a scalar value '''

    def __str__(self):
        return "Built-in: Set field to a scalar value"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # In this case we're assigning a single scalar value to all
        # elements of a field.
        field_name1  = self.array_ref(self._arguments.args[0].proxy_name)
        scalar_value = self._arguments.args[1]
        parent.add(AssignGen(parent, lhs=field_name1, rhs=scalar_value))


class DynSetvalXKern(DynBuiltIn):
    ''' Set a field equal to another field '''

    def __str__(self):
        return "Built-in: Set a field equal to another field"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We copy one element of field X (second arg) to the
        # corresponding element of field Y (first arg).
        field_name2 = self.array_ref(self._arguments.args[0].proxy_name)
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        parent.add(AssignGen(parent, lhs=field_name2, rhs=field_name1))
#---------------------------------------------------------------------#
#=============== Inner product of fields =============================#
#---------------------------------------------------------------------#
class DynXInnerproductYKern(DynBuiltIn):
    ''' Calculates the inner product of two fields,
    innprod = SUM( field1(:)*field2(:) ) '''

    def __str__(self):
        return "Built-in: X_innerproduct_Y"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We sum the DoF-wise product of the supplied fields. The variable
        # holding the sum is initialised to zero in the psy layer.
        innprod_name = self._reduction_ref(self._arguments.args[0].name)
        field_name1  = self.array_ref(self._arguments.args[1].proxy_name)
        field_name2  = self.array_ref(self._arguments.args[2].proxy_name)
        rhs_expr = innprod_name + "+" + field_name1 + "*" + field_name2
        parent.add(AssignGen(parent, lhs=innprod_name, rhs=rhs_expr))


class DynXInnerproductXKern(DynBuiltIn):
    ''' Calculates the inner product of one field by itself,
    innprod = SUM( field1(:)*field1(:) ) '''

    def __str__(self):
        return "Built-in: X_innerproduct_X"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # We sum the DoF-wise product of the supplied fields. The variable
        # holding the sum is initialised to zero in the psy layer.
        innprod_name = self._reduction_ref(self._arguments.args[0].name)
        field_name1  = self.array_ref(self._arguments.args[1].proxy_name)
        rhs_expr = innprod_name + "+" + field_name1 + "*" + field_name1
        parent.add(AssignGen(parent, lhs=innprod_name, rhs=rhs_expr))
#---------------------------------------------------------------------#
#=============== Sum field elements ==================================#
#---------------------------------------------------------------------#
class DynSumXKern(DynBuiltIn):
    ''' Computes the sum of the elements of a field '''

    def __str__(self):
        return "Built-in: sum a field"

    def gen_code(self, parent):
        from f2pygen import AssignGen
        # Sum all the elements of a field. The variable holding the
        # sum is initialised to zero in the psy layer.
        field_name1 = self.array_ref(self._arguments.args[1].proxy_name)
        sum_name    = self._reduction_ref(self._arguments.args[0].name)
        rhs_expr = sum_name + "+" + field_name1
        parent.add(AssignGen(parent, lhs=sum_name, rhs=rhs_expr))


# The built-in operations that we support for this API. The meta-data
# describing these kernels is in dynamo0p3_builtins_mod.f90. This dictionary
# can only be defined after all of the necessary 'class' statements have
# been executed (happens when this module is imported into another).
# Note: Issue #58 will introduce functionality to obtain list of supported
# built-ins from dynamo0p3_builtins_mod.f90 instead of defining them here.
BUILTIN_MAP_F90 = {# Adding (scaled) fields
                   "X_plus_Y": DynXPlusYKern, 
                   "inc_X_plus_Y": DynIncXPlusYKern,
                   "aX_plus_Y": DynAXPlusYKern, 
                   "inc_aX_plus_Y": DynIncAXPlusYKern,
                   "inc_X_plus_bY": DynIncXPlusBYKern,
                   "aX_plus_bY": DynAXPlusBYKern, 
                   "inc_aX_plus_bY": DynIncAXPlusBYKern,   
                    # Subtracting (scaled) fields
                   "X_minus_Y": DynXMinusYKern,                
                   "aX_minus_Y": DynAXMinusYKern,
                   "inc_X_minus_bY": DynIncXMinusBYKern,
                    # Multiplying (scaled) fields
                   "X_times_Y": DynXTimesYKern, 
                   "inc_X_times_Y": DynIncXTimesYKern,
                   # Multiplying fields by a scalar (scaling fields)
                   "a_times_X": DynATimesXKern, 
                   "inc_a_times_X": DynIncATimesXKern,
                   # Dividing (scaled) fields
                   "X_divideby_Y": DynXDividebyYKern, 
                   "inc_X_divideby_Y": DynIncXDividebyYKern,
                   # Raising field to a scalar                   
                   "inc_X_powreal_a": DynIncXPowrealAKern,
                   # Setting field elements to scalar or other field's values    
                   "setval_c": DynSetvalCKern,
                   "setval_X": DynSetvalXKern,           
                   # Inner product of fields
                   "X_innerproduct_Y": DynXInnerproductYKern,
                   "X_innerproduct_X": DynXInnerproductXKern,
                   # Sum values of a field
                   "sum_X": DynSumXKern} 


# Built-in map dictionary in lowercase keys for invoke generation and comparison
# purposes. This does not enforce case sensitivity to Fortran built-in names.
BUILTIN_MAP = get_builtin_map(BUILTIN_MAP_F90)
