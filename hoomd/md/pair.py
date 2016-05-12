# -- start license --
# Highly Optimized Object-oriented Many-particle Dynamics -- Blue Edition
# (HOOMD-blue) Open Source Software License Copyright 2009-2016 The Regents of
# the University of Michigan All rights reserved.

# HOOMD-blue may contain modifications ("Contributions") provided, and to which
# copyright is held, by various Contributors who have granted The Regents of the
# University of Michigan the right to modify and/or distribute such Contributions.

# You may redistribute, use, and create derivate works of HOOMD-blue, in source
# and binary forms, provided you abide by the following conditions:

# * Redistributions of source code must retain the above copyright notice, this
# list of conditions, and the following disclaimer both in the code and
# prominently in any materials provided with the distribution.

# * Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions, and the following disclaimer in the documentation and/or
# other materials provided with the distribution.

# * All publications and presentations based on HOOMD-blue, including any reports
# or published results obtained, in whole or in part, with HOOMD-blue, will
# acknowledge its use according to the terms posted at the time of submission on:
# http://codeblue.umich.edu/hoomd-blue/citations.html

# * Any electronic documents citing HOOMD-Blue will link to the HOOMD-Blue website:
# http://codeblue.umich.edu/hoomd-blue/

# * Apart from the above required attributions, neither the name of the copyright
# holder nor the names of HOOMD-blue's contributors may be used to endorse or
# promote products derived from this software without specific prior written
# permission.

# Disclaimer

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND/OR ANY
# WARRANTIES THAT THIS SOFTWARE IS FREE OF INFRINGEMENT ARE DISCLAIMED.

# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# -- end license --

# Maintainer: joaander / All Developers are free to add commands for new features

R""" Pair potentials.

Generally, pair forces are short range and are summed over all non-bonded particles
within a certain cutoff radius of each particle. Any number of pair forces
can be defined in a single simulation. The net force on each particle due to
all types of pair forces is summed.

Pair forces require that parameters be set for each unique type pair. Coefficients
are set through the aid of the :py:class:`coeff` class. To set this coefficients, specify
a pair force and save it in a variable::

    my_force = pair.some_pair_force(arguments...)

Then the coefficients can be set using the saved variable::

    my_force.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0)
    my_force.pair_coeff.set('A', 'B', epsilon=1.0, sigma=2.0)
    my_force.pair_coeff.set('B', 'B', epsilon=2.0, sigma=1.0)

This example set the parameters *epsilon* and *sigma*
(which are used in :py:class:`lj`). Different pair forces require that different
coefficients are set. Check the documentation of each to see the definition
of the coefficients.
"""

from hoomd import _hoomd
from hoomd.md import _md
from hoomd.md import force;
from hoomd.md import nlist as nl # to avoid naming conflicts
import hoomd;

import math;
import sys;

from collections import OrderedDict

class coeff:
    R""" Define pair coefficients

    All pair forces use :py:class:`coeff` to specify the coefficients between different
    pairs of particles indexed by type. The set of pair coefficients is a symmetric
    matrix defined over all possible pairs of particle types.

    There are two ways to set the coefficients for a particular pair force.
    The first way is to save the pair force in a variable and call :py:meth:`set()` directly.

    The second method is to build the :py:class:`coeff` class first and then assign it to the
    pair force. There are some advantages to this method in that you could specify a
    complicated set of pair coefficients in a separate python file and import it into
    your job script.

    Example (**force_field.py**)::

        from hoomd import md
        my_coeffs = md.pair.coeff();
        my_force.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0)
        my_force.pair_coeff.set('A', 'B', epsilon=1.0, sigma=2.0)
        my_force.pair_coeff.set('B', 'B', epsilon=2.0, sigma=1.0)

    Example job script::

        from hoomd import md
        import force_field

        .....
        my_force = md.pair.some_pair_force(arguments...)
        my_force.pair_coeff = force_field.my_coeffs

    """

    ## \internal
    # \brief Initializes the class
    # \details
    # The main task to be performed during initialization is just to init some variables
    # \param self Python required class instance variable
    def __init__(self):
        self.values = {};
        self.default_coeff = {}

    ## \internal
    # \brief Return a compact representation of the pair coefficients
    def get_metadata(self):
        # return list for easy serialization
        l = []
        for (a,b) in self.values:
            item = OrderedDict()
            item['typei'] = a
            item['typej'] = b
            for coeff in self.values[(a,b)]:
                item[coeff] = self.values[(a,b)][coeff]
            l.append(item)
        return l

    ## \var values
    # \internal
    # \brief Contains the matrix of set values in a dictionary

    ## \var default_coeff
    # \internal
    # \brief default_coeff['coeff'] lists the default value for \a coeff, if it is set

    ## \internal
    # \brief Sets a default value for a given coefficient
    # \details
    # \param name Name of the coefficient to for which to set the default
    # \param value Default value to set
    #
    # Some coefficients have reasonable default values and the user should not be burdened with typing them in
    # all the time. set_default_coeff() sets
    def set_default_coeff(self, name, value):
        self.default_coeff[name] = value;

    def set(self, a, b, **coeffs):
        R""" Sets parameters for one type pair.

        Args:
            a (str): First particle type in the pair (or a list of type names)
            b (str): Second particle type in the pair (or a list of type names)
            coeffs: Named coefficients (see below for examples)

        Calling :py:meth:`set()` results in one or more parameters being set for a single type pair
        or set of type pairs.
        Particle types are identified by name, and parameters are also added by name.
        Which parameters you need to specify depends on the pair force you are setting
        these coefficients for, see the corresponding documentation.

        All possible type pairs as defined in the simulation box must be specified before
        executing :py:class:`run()`. You will receive an error if you fail to do so. It is not an error,
        however, to specify coefficients for particle types that do not exist in the simulation.
        This can be useful in defining a force field for many different types of particles even
        when some simulations only include a subset.

        There is no need to specify coefficients for both pairs 'A', 'B' and 'B', 'A'. Specifying
        only one is sufficient.

        To set the same coefficients between many particle types, provide a list of type names instead of a single
        one. All pairs between the two lists will be set to the same parameters.

        Examples::

            coeff.set('A', 'A', epsilon=1.0, sigma=1.0)
            coeff.set('B', 'B', epsilon=2.0, sigma=1.0)
            coeff.set('A', 'B', epsilon=1.5, sigma=1.0)
            coeff.set(['A', 'B', 'C', 'D'], 'F', epsilon=2.0)
            coeff.set(['A', 'B', 'C', 'D'], ['A', 'B', 'C', 'D'], epsilon=1.0)

            system = init.read_xml('init.xml')
            coeff.set(system.particles.types, system.particles.types, epsilon=2.0)
            coeff.set('A', system.particles.types, epsilon=1.2)

        Note:
            Single parameters can be updated. If both epsilon and sigma have already been
            set for a type pair, then executing ``coeff.set('A', 'B', epsilon=1.1)`` will update
            the value of epsilon and leave sigma as it was previously set.

        Some pair potentials assign default values to certain parameters. If the default setting for a given coefficient
        (as documented in the respective pair command) is not set explicitly, the default will be used.

        """
        hoomd.util.print_status_line();

        # listify the inputs
        if isinstance(a, str):
            a = [a];
        if isinstance(b, str):
            b = [b];

        for ai in a:
            for bi in b:
                self.set_single(ai, bi, coeffs);

    ## \internal
    # \brief Sets a single parameter
    def set_single(self, a, b, coeffs):
        a = str(a);
        b = str(b);

        # create the pair if it hasn't been created it
        if (not (a,b) in self.values) and (not (b,a) in self.values):
            self.values[(a,b)] = {};

        # Find the pair to update
        if (a,b) in self.values:
            cur_pair = (a,b);
        elif (b,a) in self.values:
            cur_pair = (b,a);
        else:
            hoomd.context.msg.error("Bug detected in pair.coeff. Please report\n");
            raise RuntimeError("Error setting pair coeff");

        # update each of the values provided
        if len(coeffs) == 0:
            hoomd.context.msg.error("No coefficents specified\n");
        for name, val in coeffs.items():
            self.values[cur_pair][name] = val;

        # set the default values
        for name, val in self.default_coeff.items():
            # don't override a coeff if it is already set
            if not name in self.values[cur_pair]:
                self.values[cur_pair][name] = val;

    ## \internal
    # \brief Verifies set parameters form a full matrix with all values set
    # \details
    # \param self Python required self variable
    # \param required_coeffs list of required variables
    #
    # This can only be run after the system has been initialized
    def verify(self, required_coeffs):
        # first, check that the system has been initialized
        if not hoomd.init.is_initialized():
            hoomd.context.msg.error("Cannot verify pair coefficients before initialization\n");
            raise RuntimeError('Error verifying pair coefficients');

        # get a list of types from the particle data
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        valid = True;
        # loop over all possible pairs and verify that all required variables are set
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                a = type_list[i];
                b = type_list[j];

                # find which half of the pair is set
                if (a,b) in self.values:
                    cur_pair = (a,b);
                elif (b,a) in self.values:
                    cur_pair = (b,a);
                else:
                    hoomd.context.msg.error("Type pair " + str((a,b)) + " not found in pair coeff\n");
                    valid = False;
                    continue;

                # verify that all required values are set by counting the matches
                count = 0;
                for coeff_name in self.values[cur_pair].keys():
                    if not coeff_name in required_coeffs:
                        hoomd.context.msg.notice(2, "Notice: Possible typo? Pair coeff " + str(coeff_name) + " is specified for pair " + str((a,b)) + \
                              ", but is not used by the pair force\n");
                    else:
                        count += 1;

                if count != len(required_coeffs):
                    hoomd.context.msg.error("Type pair " + str((a,b)) + " is missing required coefficients\n");
                    valid = False;


        return valid;

    ## \internal
    # \brief Try to get whether a single pair coefficient
    # \detail
    # \param a First name in the type pair
    # \param b Second name in the type pair
    # \param coeff_name Coefficient to get
    def get(self,a,b,coeff_name):
        if (a,b) in self.values:
            cur_pair = (a,b);
        elif (b,a) in self.values:
            cur_pair = (b,a);
        else:
            return None;

        if coeff_name in self.values[cur_pair]:
            return self.values[cur_pair][coeff_name];
        else:
            return None;

class pair(force._force):
    R""" Common pair potential documentation.

    Users should not invoke :py:class:`pair` directly. It is a base command that provides common
    features to all standard pair forces. Common documentation for all pair potentials is documented here.

    All pair force commands specify that a given potential energy and force be computed on all non-excluded particle
    pairs in the system within a short range cutoff distance :math:`r_{\mathrm{cut}}`.

    The force :math:`\vec{F}` applied between each pair of particles is:

    .. math::
        :nowrap:

        \begin{eqnarray*}
        \vec{F}  = & -\nabla V(r) & r < r_{\mathrm{cut}} \\
                  = & 0           & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    where :math:`\vec{r}` is the vector pointing from one particle to the other in the pair, and :math:`V(r)` is
    chosen by a mode switch (see :py:meth:`set_params()`):

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V(r)  = & V_{\mathrm{pair}}(r) & \mathrm{mode\ is\ no\_shift} \\
              = & V_{\mathrm{pair}}(r) - V_{\mathrm{pair}}(r_{\mathrm{cut}}) & \mathrm{mode\ is\ shift} \\
              = & S(r) \cdot V_{\mathrm{pair}}(r) & \mathrm{mode\ is\ xplor\ and\ } r_{\mathrm{on}} < r_{\mathrm{cut}} \\
              = & V_{\mathrm{pair}}(r) - V_{\mathrm{pair}}(r_{\mathrm{cut}}) & \mathrm{mode\ is\ xplor\ and\ } r_{\mathrm{on}} \ge r_{\mathrm{cut}}
        \end{eqnarray*}

    :math:`S(r)` is the XPLOR smoothing function:

    .. math::
        :nowrap:

        \begin{eqnarray*}
        S(r) = & 1 & r < r_{\mathrm{on}} \\
             = & \frac{(r_{\mathrm{cut}}^2 - r^2)^2 \cdot (r_{\mathrm{cut}}^2 + 2r^2 -
                 3r_{\mathrm{on}}^2)}{(r_{\mathrm{cut}}^2 - r_{\mathrm{on}}^2)^3}
               & r_{\mathrm{on}} \le r \le r_{\mathrm{cut}} \\
             = & 0 & r > r_{\mathrm{cut}} \\
         \end{eqnarray*}

    and :math:`V_{\mathrm{pair}}(r)` is the specific pair potential chosen by the respective command.

    Enabling the XPLOR smoothing function :math:`S(r)` results in both the potential energy and the force going smoothly
    to 0 at :math:`r = r_{\mathrm{cut}}`, reducing the rate of energy drift in long simulations.
    :math:`r_{\mathrm{on}}` controls the point at which the smoothing starts, so it can be set to only slightly modify
    the tail of the potential. It is suggested that you plot your potentials with various values of
    :math:`r_{\mathrm{on}}` in order to find a good balance between a smooth potential function and minimal modification
    of the original :math:`V_{\mathrm{pair}}(r)`. A good value for the LJ potential is
    :math:`r_{\mathrm{on}} = 2 \cdot \sigma`.

    The split smoothing / shifting of the potential when the mode is ``xplor`` is designed for use in mixed WCA / LJ
    systems. The WCA potential and it's first derivative already go smoothly to 0 at the cutoff, so there is no need
    to apply the smoothing function. In such mixed systems, set :math:`r_{\mathrm{on}}` to a value greater than
    :math:`r_{\mathrm{cut}}` for those pairs that interact via WCA in order to enable shifting of the WCA potential
    to 0 at the cuttoff.

    The following coefficients must be set per unique pair of particle types. See :py:mod:`hoomd.pair` for information
    on how to set coefficients:

    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}` - *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    When :math:`r_{\mathrm{cut}} \le 0` or is set to False, the particle type pair interaction is excluded from the neighbor
    list. This mechanism can be used in conjunction with multiple neighbor lists to make efficient calculations in systems
    with large size disparity. Functionally, this is equivalent to setting :math:`r_{\mathrm{cut}} = 0` in the pair force
    because negative :math:`r_{\mathrm{cut}}` has no physical meaning.
    """

    ## \internal
    # \brief Initialize the pair force
    # \details
    # The derived class must set
    #  - self.cpp_class (the pair class to instantiate)
    #  - self.required_coeffs (a list of the coeff names the derived class needs)
    #  - self.process_coeffs() (a method that takes in the coeffs and spits out a param struct to use in
    #       self.cpp_force.set_params())
    def __init__(self, r_cut, nlist, name=None):
        # initialize the base class
        force._force.__init__(self, name);

        # convert r_cut False to a floating point type
        if r_cut is False:
            r_cut = -1.0
        self.global_r_cut = r_cut;

        # setup the coefficent matrix
        self.pair_coeff = coeff();
        self.pair_coeff.set_default_coeff('r_cut', self.global_r_cut);
        self.pair_coeff.set_default_coeff('r_on', self.global_r_cut);

        # setup the neighbor list
        self.nlist = nlist
        self.nlist.subscribe(lambda:self.get_rcut())
        self.nlist.update_rcut()

    def set_params(self, mode=None):
        R""" Set parameters controlling the way forces are computed.

        Args:
            mode (str): (if set) Set the mode with which potentials are handled at the cutoff.

        Valid values for *mode* are: "none" (the default), "shift", and "xplor":

        - **none** - No shifting is performed and potentials are abruptly cut off
        - **shift** - A constant shift is applied to the entire potential so that it is 0 at the cutoff
        - **xplor** - A smoothing function is applied to gradually decrease both the force and potential to 0 at the
          cutoff when ron < rcut, and shifts the potential to 0 at the cutoff when ron >= rcut.

        See :py:class:`pair` for the equations.

        Examples::

            mypair.set_params(mode="shift")
            mypair.set_params(mode="no_shift")
            mypair.set_params(mode="xplor")

        """
        hoomd.util.print_status_line();

        if mode is not None:
            if mode == "no_shift":
                self.cpp_force.setShiftMode(self.cpp_class.energyShiftMode.no_shift)
            elif mode == "shift":
                self.cpp_force.setShiftMode(self.cpp_class.energyShiftMode.shift)
            elif mode == "xplor":
                self.cpp_force.setShiftMode(self.cpp_class.energyShiftMode.xplor)
            else:
                hoomd.context.msg.error("Invalid mode\n");
                raise RuntimeError("Error changing parameters in pair force");

    def process_coeff(self, coeff):
        hoomd.context.msg.error("Bug in hoomd_script, please report\n");
        raise RuntimeError("Error processing coefficients");

    def update_coeffs(self):
        coeff_list = self.required_coeffs + ["r_cut", "r_on"];
        # check that the pair coefficents are valid
        if not self.pair_coeff.verify(coeff_list):
            hoomd.context.msg.error("Not all pair coefficients are set\n");
            raise RuntimeError("Error updating pair coefficients");

        # set all the params
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # build a dict of the coeffs to pass to process_coeff
                coeff_dict = {};
                for name in coeff_list:
                    coeff_dict[name] = self.pair_coeff.get(type_list[i], type_list[j], name);

                param = self.process_coeff(coeff_dict);
                self.cpp_force.setParams(i, j, param);

                # rcut can now have "invalid" C++ values, which we round up to zero
                self.cpp_force.setRcut(i, j, max(coeff_dict['r_cut'], 0.0));
                self.cpp_force.setRon(i, j, max(coeff_dict['r_on'], 0.0));

    ## \internal
    # \brief Get the maximum r_cut value set for any type pair
    # \pre update_coeffs must be called before get_max_rcut to verify that the coeffs are set
    def get_max_rcut(self):
        # go through the list of only the active particle types in the sim
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # find the maximum r_cut
        max_rcut = 0.0;

        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # get the r_cut value
                r_cut = self.pair_coeff.get(type_list[i], type_list[j], 'r_cut');
                max_rcut = max(max_rcut, r_cut);

        return max_rcut;

    ## \internal
    # \brief Get the r_cut pair dictionary
    # \returns The rcut(i,j) dict if logging is on, and None if logging is off
    def get_rcut(self):
        if not self.log:
            return None

        # go through the list of only the active particle types in the sim
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # update the rcut by pair type
        r_cut_dict = nl.rcut();
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # get the r_cut value
                r_cut = self.pair_coeff.get(type_list[i], type_list[j], 'r_cut');

                if r_cut is not None: # use the defined value
                    if r_cut is False: # interaction is turned off
                        r_cut_dict.set_pair(type_list[i],type_list[j], -1.0);
                    else:
                        r_cut_dict.set_pair(type_list[i],type_list[j], r_cut);
                else: # use the global default
                    r_cut_dict.set_pair(type_list[i],type_list[j],self.global_r_cut);

        return r_cut_dict;

    ## \internal
    # \brief Return metadata for this pair potential
    def get_metadata(self):
        data = force._force.get_metadata(self)

        # make sure all coefficients are set
        self.update_coeffs()

        data['pair_coeff'] = self.pair_coeff
        return data

    def compute_energy(self, tags1, tags2):
        R""" Compute the energy between two sets of particles.

        Args:
            tags1 (ndarray<int32>): a numpy array of particle tags in the first group
            tags2 (ndarray<int32>): a numpy array of particle tags in the second group

        .. math::

            U = \sum_{i \in \mathrm{tags1}, j \in \mathrm{tags2}} V_{ij}(r)

        where :math:`V_{ij}(r)` is the pairwise energy between two particles :math:`i` and :math:`j`.

        Assumed properties of the sets *tags1* and *tags2* are:

        - *tags1* and *tags2* are disjoint
        - all elements in *tags1* and *tags2* are unique
        - *tags1* and *tags2* are contiguous numpy arrays of dtype int32

        None of these properties are validated.

        Examples::

            tags=numpy.linspace(0,N-1,1, dtype=numpy.int32)
            # computes the energy between even and odd particles
            U = mypair.compute_energy(tags1=numpy.array(tags[0:N:2]), tags2=numpy.array(tags[1:N:2]))

        """
        # future versions could use np functions to test the assumptions above and raise an error if they occur.
        return self.cpp_force.computeEnergyBetweenSets(tags1, tags2);

class lj(pair):
    R""" Lennard-Jones pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`lj` specifies that a Lennard-Jones pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{LJ}}(r)  = & 4 \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{12} -
                          \alpha \left( \frac{\sigma}{r} \right)^{6} \right] & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`\alpha` - *alpha* (unitless) - *optional*: defaults to 1.0
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        lj = pair.lj(r_cut=3.0, nlist=nl)
        lj.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0)
        lj.pair_coeff.set('A', 'B', epsilon=2.0, sigma=1.0, alpha=0.5, r_cut=3.0, r_on=2.0);
        lj.pair_coeff.set('B', 'B', epsilon=1.0, sigma=1.0, r_cut=2**(1.0/6.0), r_on=2.0);
        lj.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon=1.5, sigma=2.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairLJ(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairLJ;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairLJGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairLJGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'sigma', 'alpha'];
        self.pair_coeff.set_default_coeff('alpha', 1.0);

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        sigma = coeff['sigma'];
        alpha = coeff['alpha'];

        lj1 = 4.0 * epsilon * math.pow(sigma, 12.0);
        lj2 = alpha * 4.0 * epsilon * math.pow(sigma, 6.0);
        return _hoomd.make_scalar2(lj1, lj2);

class gauss(pair):
    R""" Gaussian pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`gauss` specifies that a Gaussian pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{gauss}}(r)  = & \varepsilon \exp \left[ -\frac{1}{2}\left( \frac{r}{\sigma} \right)^2 \right]
                                                & r < r_{\mathrm{cut}} \\
                               = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        gauss = pair.gauss(r_cut=3.0, nlist=nl)
        gauss.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0)
        gauss.pair_coeff.set('A', 'B', epsilon=2.0, sigma=1.0, r_cut=3.0, r_on=2.0);
        gauss.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon=3.0, sigma=0.5)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairGauss(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairGauss;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairGaussGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairGaussGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'sigma'];

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        sigma = coeff['sigma'];

        return _hoomd.make_scalar2(epsilon, sigma);

class slj(pair):
    R""" Shifted Lennard-Jones pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.
        d_max (float): Maximum diameter particles in the simulation will have (in distance units)

    :py:class:`slj` specifies that a shifted Lennard-Jones type pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{SLJ}}(r)  = & 4 \varepsilon \left[ \left( \frac{\sigma}{r - \Delta} \right)^{12} -
                               \left( \frac{\sigma}{r - \Delta} \right)^{6} \right] & r < (r_{\mathrm{cut}} + \Delta) \\
                             = & 0 & r \ge (r_{\mathrm{cut}} + \Delta) \\
        \end{eqnarray*}

    where :math:`\Delta = (d_i + d_j)/2 - 1` and :math:`d_i` is the diameter of particle :math:`i`.

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
      - *optional*: defaults to 1.0
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    .. attention::
        Due to the way that pair.slj modifies the cutoff criteria, a shift_mode of *xplor* is not supported.

    The actual cutoff radius for pair.slj is shifted by the diameter of two particles interacting.  Thus to determine
    the maximum possible actual r_cut in simulation
    pair.slj must know the maximum diameter of all the particles over the entire run, *d_max* .
    This value is either determined automatically from the initialization or can be set by the user and can be
    modified between runs with :py:meth:`hoomd.md.nlist.nlist.set_params()`. In most cases, the correct value can be
    identified automatically.

    The specified value of *d_max* will be used to properly determine the neighbor lists during the following
    :py:func:`hoomd.run()` commands. If not specified, :py:class:`slj` will set d_max to the largest diameter
    in particle data at the time it is initialized.

    If particle diameters change after initialization, it is **imperative** that *d_max* be the largest
    diameter that any particle will attain at any time during the following :py:func:`hoomd.run()` commands.
    If *d_max* is smaller than it should be, some particles will effectively have a smaller value of *r_cut*
    then was set and the simulation will be incorrect. *d_max* can be changed between runs by calling
    :py:meth:`hoomd.md.nlist.nlist.set_params()`.

    Example::

        nl = nlist.cell()
        slj = pair.slj(r_cut=3.0, nlist=nl, d_max = 2.0)
        slj.pair_coeff.set('A', 'A', epsilon=1.0)
        slj.pair_coeff.set('A', 'B', epsilon=2.0, r_cut=3.0);
        slj.pair_coeff.set('B', 'B', epsilon=1.0, r_cut=2**(1.0/6.0));
        slj.pair_coeff.set(['A', 'B'], ['C', 'D'], espilon=2.0)

    """
    def __init__(self, r_cut, nlist, d_max=None, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # update the neighbor list
        if d_max is None :
            sysdef = hoomd.context.current.system_definition;
            d_max = sysdef.getParticleData().getMaxDiameter()
            hoomd.context.msg.notice(2, "Notice: slj set d_max=" + str(d_max) + "\n");

        # SLJ requires diameter shifting to be on
        self.nlist.cpp_nlist.setDiameterShift(True);
        self.nlist.cpp_nlist.setMaximumDiameter(d_max);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairSLJ(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairSLJ;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairSLJGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairSLJGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficient options
        self.required_coeffs = ['epsilon', 'sigma', 'alpha'];
        self.pair_coeff.set_default_coeff('alpha', 1.0);

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        sigma = coeff['sigma'];
        alpha = coeff['alpha'];

        lj1 = 4.0 * epsilon * math.pow(sigma, 12.0);
        lj2 = alpha * 4.0 * epsilon * math.pow(sigma, 6.0);
        return _hoomd.make_scalar2(lj1, lj2);

    def set_params(self, mode=None):
        R""" Set parameters controlling the way forces are computed.

        See :py:meth:`pair.set_params()`.

        Note:
            **xplor** is not a valid setting for :py:class:`slj`.

        """
        hoomd.util.print_status_line();

        if mode == "xplor":
            hoomd.context.msg.error("XPLOR is smoothing is not supported with slj\n");
            raise RuntimeError("Error changing parameters in pair force");

        pair.set_params(self, mode=mode);

class yukawa(pair):
    R""" Yukawa pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`yukawa` specifies that a Yukawa pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
         V_{\mathrm{yukawa}}(r)  = & \varepsilon \frac{ \exp \left( -\kappa r \right) }{r} & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\kappa` - *kappa* (in units of 1/distance)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        yukawa = pair.lj(r_cut=3.0, nlist=nl)
        yukawa.pair_coeff.set('A', 'A', epsilon=1.0, kappa=1.0)
        yukawa.pair_coeff.set('A', 'B', epsilon=2.0, kappa=0.5, r_cut=3.0, r_on=2.0);
        yukawa.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon=0.5, kappa=3.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairYukawa(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairYukawa;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairYukawaGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairYukawaGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'kappa'];

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        kappa = coeff['kappa'];

        return _hoomd.make_scalar2(epsilon, kappa);

class ewald(pair):
    R""" Ewald pair potential.

    :py:class:`ewald` specifies that a Ewald pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
         V_{\mathrm{ewald}}(r)  = & q_i q_j \mathrm{erfc}(\kappa r)/r & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\kappa` - *kappa* (in 1/distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command


    Example::

        nl = nlist.cell()
        ewald = pair.ewald(r_cut=3.0, nlist=nl)
        ewald.pair_coeff.set('A', 'A', kappa=1.0)
        ewald.pair_coeff.set('A', 'B', kappa=1.0, r_cut=3.0, r_on=2.0);

    Warning:
        **DO NOT** use in conjunction with :py:class:`hoomd.md.charge.pppm`. It automatically creates and configures
        :py:class:`ewald` for you.

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairEwald(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairEwald;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairEwaldGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairEwaldGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['kappa'];

    def process_coeff(self, coeff):
        kappa = coeff['kappa'];

        return kappa;

class cgcmm(force._force):
    R""" CMM coarse-grain model pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list

    :py:class:`cgcmm` specifies that a special version of Lennard-Jones pair force
    should be added to every non-bonded particle pair in the simulation. This potential
    version is used in the CMM coarse grain model and uses a combination of Lennard-Jones
    potentials with different exponent pairs between different atom pairs.

    `B. Levine et. al. 2011 <http://dx.doi.org/10.1021/ct2005193>`_ describes the CGCMM implementation details in
    HOOMD-blue. Cite it if you utilize the CGCMM potential in your work.

    Multiple potential functions can be selected:

    .. math::

        V_{\mathrm{LJ}}(r) = 4 \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{12} -
                                                  \alpha \left( \frac{\sigma}{r} \right)^{6} \right]

        V_{\mathrm{LJ}}(r) = \frac{27}{4} \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{9} -
                                                             \alpha \left( \frac{\sigma}{r} \right)^{6} \right]

        V_{\mathrm{LJ}}(r) = \frac{3\sqrt{3}}{2} \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{12} -
                                                               \alpha \left( \frac{\sigma}{r} \right)^{4} \right]

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`\alpha` - *alpha* (unitless) - *optional*: defaults to 1.0
    - exponents, the choice of LJ-exponents, currently supported are 12-6, 9-6, and 12-4.

    We support three keyword variants 124 (native), lj12_4 (LAMMPS), LJ12-4 (MPDyn).

    Example::

        nl = nlist.cell()
        cg = pair.cgcmm(r_cut=3.0, nlist=nl)
        cg.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0, alpha=1.0, exponents='LJ12-6')
        cg.pair_coeff.set('W', 'W', epsilon=3.7605, sigma=1.285588, alpha=1.0, exponents='lj12_4')
        cg.pair_coeff.set('OA', 'OA', epsilon=1.88697479, sigma=1.09205882, alpha=1.0, exponents='96')

    """
    def __init__(self, r_cut, nlist):
        hoomd.util.print_status_line();

        # Error out in MPI simulations
        if (_hoomd.is_MPI_available()):
            if hoomd.context.current.system_definition.getParticleData().getDomainDecomposition():
                hoomd.context.msg.error("pair.cgcmm is not supported in multi-processor simulations.\n\n")
                raise RuntimeError("Error setting up pair potential.")

        # initialize the base class
        force._force.__init__(self);

        # this class extends force, so we need to store the r_cut explicitly as a member
        # to be used in get_rcut
        # the authors of this potential also did not incorporate pairwise cutoffs, so we just use
        # the same number for everything
        self.r_cut = r_cut

        # setup the coefficent matrix
        self.pair_coeff = coeff();

        # if no neighbor list is supplied, use the default global neighborlist
        if nlist is None:
            self.nlist = nl._subscribe_global_nlist(lambda:self.get_rcut())
        else: # otherwise, subscribe the specified neighbor list
            self.nlist = nlist
            self.nlist.subscribe(lambda:self.get_rcut())
            self.nlist.update_rcut()

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.CGCMMForceCompute(hoomd.context.current.system_definition, self.nlist.cpp_nlist, r_cut);
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.CGCMMForceComputeGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, r_cut);
            self.cpp_force.setBlockSize(128);

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

    def get_rcut(self):
        if not self.log:
            return None

        # go through the list of only the active particle types in the sim
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # update the rcut by pair type
        r_cut_dict = nl.rcut();
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                r_cut_dict.set_pair(type_list[i],type_list[j],self.r_cut);

        return r_cut_dict;

    def update_coeffs(self):
        # check that the pair coefficents are valid
        if not self.pair_coeff.verify(["epsilon", "sigma", "alpha", "exponents"]):
            hoomd.context.msg.error("Not all pair coefficients are set in pair.cgcmm\n");
            raise RuntimeError("Error updating pair coefficients");

        # set all the params
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        for i in range(0,ntypes):
            for j in range(i,ntypes):
                epsilon = self.pair_coeff.get(type_list[i], type_list[j], "epsilon");
                sigma = self.pair_coeff.get(type_list[i], type_list[j], "sigma");
                alpha = self.pair_coeff.get(type_list[i], type_list[j], "alpha");
                exponents = self.pair_coeff.get(type_list[i], type_list[j], "exponents");
                # we support three variants 124 (native), lj12_4 (LAMMPS), LJ12-4 (MPDyn)
                if (exponents == 124) or  (exponents == 'lj12_4') or  (exponents == 'LJ12-4') :
                    prefactor = 2.59807621135332
                    lja = prefactor * epsilon * math.pow(sigma, 12.0);
                    ljb = -alpha * prefactor * epsilon * math.pow(sigma, 4.0);
                    self.cpp_force.setParams(i, j, lja, 0.0, 0.0, ljb);
                elif (exponents == 96) or  (exponents == 'lj9_6') or  (exponents == 'LJ9-6') :
                    prefactor = 6.75
                    lja = prefactor * epsilon * math.pow(sigma, 9.0);
                    ljb = -alpha * prefactor * epsilon * math.pow(sigma, 6.0);
                    self.cpp_force.setParams(i, j, 0.0, lja, ljb, 0.0);
                elif (exponents == 126) or  (exponents == 'lj12_6') or  (exponents == 'LJ12-6') :
                    prefactor = 4.0
                    lja = prefactor * epsilon * math.pow(sigma, 12.0);
                    ljb = -alpha * prefactor * epsilon * math.pow(sigma, 6.0);
                    self.cpp_force.setParams(i, j, lja, 0.0, ljb, 0.0);
                else:
                    raise RuntimeError("Unknown exponent type.  Must be one of MN, ljM_N, LJM-N with M+N in 12+4, 9+6, or 12+6");

def _table_eval(r, rmin, rmax, V, F, width):
    dr = (rmax - rmin) / float(width-1);
    i = int(round((r - rmin)/dr))
    return (V[i], F[i])

class table(force._force):
    R""" Tabulated pair potential.

    Args:
        width (int): Number of points to use to interpolate V and F.
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list (default of None automatically creates a global cell-list based neighbor list)
        name (str): Name of the force instance

    :py:class:`table` specifies that a tabulated pair potential should be applied between every
    non-excluded particle pair in the simulation.

    The force :math:`\vec{F}` is (in force units):

    .. math::
        :nowrap:

        \begin{eqnarray*}
        \vec{F}(\vec{r})     = & 0                           & r < r_{\mathrm{min}} \\
                             = & F_{\mathrm{user}}(r)\hat{r} & r_{\mathrm{min}} \le r < r_{\mathrm{max}} \\
                             = & 0                           & r \ge r_{\mathrm{max}} \\
        \end{eqnarray*}

    and the potential :math:`V(r)` is (in energy units)

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V(r)       = & 0                    & r < r_{\mathrm{min}} \\
                   = & V_{\mathrm{user}}(r) & r_{\mathrm{min}} \le r < r_{\mathrm{max}} \\
                   = & 0                    & r \ge r_{\mathrm{max}} \\
        \end{eqnarray*}

    where :math:`\vec{r}` is the vector pointing from one particle to the other in the pair.

    :math:`F_{\mathrm{user}}(r)` and :math:`V_{\mathrm{user}}(r)` are evaluated on *width* grid points between
    :math:`r_{\mathrm{min}}` and :math:`r_{\mathrm{max}}`. Values are interpolated linearly between grid points.
    For correctness, you must specify the force defined by: :math:`F = -\frac{\partial V}{\partial r}`.

    The following coefficients must be set per unique pair of particle types:

    - :math:`V_{\mathrm{user}}(r)` and :math:`F_{\mathrm{user}}(r)` - evaluated by ``func`` (see example)
    - coefficients passed to ``func`` - *coeff* (see example)
    - :math:`_{\mathrm{min}}` - *rmin* (in distance units)
    - :math:`_{\mathrm{max}}` - *rmax* (in distance units)

    .. rubric:: Set table from a given function

    When you have a functional form for V and F, you can enter that
    directly into python. :py:class:`table` will evaluate the given function over *width* points between
    *rmin* and *rmax* and use the resulting values in the table::

        def lj(r, rmin, rmax, epsilon, sigma):
            V = 4 * epsilon * ( (sigma / r)**12 - (sigma / r)**6);
            F = 4 * epsilon / r * ( 12 * (sigma / r)**12 - 6 * (sigma / r)**6);
            return (V, F)

        table = pair.table(width=1000)
        table.pair_coeff.set('A', 'A', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=1.5, sigma=1.0))
        table.pair_coeff.set('A', 'B', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=2.0, sigma=1.2))
        table.pair_coeff.set('B', 'B', func=lj, rmin=0.8, rmax=3.0, coeff=dict(epsilon=0.5, sigma=1.0))

    .. rubric:: Set a table from a file

    When you have no function for for *V* or *F*, or you otherwise have the data listed in a file,
    :py:class:`table` can use the given values directly. You must first specify the number of rows
    in your tables when initializing pair.table. Then use :py:meth:`set_from_file()` to read the file::

        nl = nlist.cell()
        table = pair.table(width=1000, nlist=nl)
        table.set_from_file('A', 'A', filename='table_AA.dat')
        table.set_from_file('A', 'B', filename='table_AB.dat')
        table.set_from_file('B', 'B', filename='table_BB.dat')

    Note:
        For potentials that diverge near r=0, make sure to set *rmin* to a reasonable value. If a potential does
        not diverge near r=0, then a setting of *rmin=0* is valid.

    """
    def __init__(self, width, nlist, name=None):
        hoomd.util.print_status_line();

        # initialize the base class
        force._force.__init__(self, name);

        # setup the coefficent matrix
        self.pair_coeff = coeff();

        # if no neighbor list is supplied, use the default global neighborlist
        if nlist is None:
            self.nlist = nl._subscribe_global_nlist(lambda:self.get_rcut())
        else: # otherwise, subscribe the specified neighbor list
            self.nlist = nlist
            self.nlist.subscribe(lambda:self.get_rcut())
            self.nlist.update_rcut()

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.TablePotential(hoomd.context.current.system_definition, self.nlist.cpp_nlist, int(width), self.name);
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.TablePotentialGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, int(width), self.name);

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # stash the width for later use
        self.width = width;

    def update_pair_table(self, typei, typej, func, rmin, rmax, coeff):
        # allocate arrays to store V and F
        Vtable = _hoomd.std_vector_scalar();
        Ftable = _hoomd.std_vector_scalar();

        # calculate dr
        dr = (rmax - rmin) / float(self.width-1);

        # evaluate each point of the function
        for i in range(0, self.width):
            r = rmin + dr * i;
            (V,F) = func(r, rmin, rmax, **coeff);

            # fill out the tables
            Vtable.append(V);
            Ftable.append(F);

        # pass the tables on to the underlying cpp compute
        self.cpp_force.setTable(typei, typej, Vtable, Ftable, rmin, rmax);

    ## \internal
    # \brief Get the r_cut pair dictionary
    # \returns rcut(i,j) dict if logging is on, and None otherwise
    def get_rcut(self):
        if not self.log:
            return None

        # go through the list of only the active particle types in the sim
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # update the rcut by pair type
        r_cut_dict = nl.rcut();
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # get the r_cut value
                rmax = self.pair_coeff.get(type_list[i], type_list[j], 'rmax');
                r_cut_dict.set_pair(type_list[i],type_list[j], rmax);

        return r_cut_dict;

    def get_max_rcut(self):
        # loop only over current particle types
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # find the maximum rmax to update the neighbor list with
        maxrmax = 0.0;

        # loop through all of the unique type pairs and find the maximum rmax
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                rmax = self.pair_coeff.get(type_list[i], type_list[j], "rmax");
                maxrmax = max(maxrmax, rmax);

        return maxrmax;

    def update_coeffs(self):
        # check that the pair coefficents are valid
        if not self.pair_coeff.verify(["func", "rmin", "rmax", "coeff"]):
            hoomd.context.msg.error("Not all pair coefficients are set for pair.table\n");
            raise RuntimeError("Error updating pair coefficients");

        # set all the params
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        # loop through all of the unique type pairs and evaluate the table
        for i in range(0,ntypes):
            for j in range(i,ntypes):
                func = self.pair_coeff.get(type_list[i], type_list[j], "func");
                rmin = self.pair_coeff.get(type_list[i], type_list[j], "rmin");
                rmax = self.pair_coeff.get(type_list[i], type_list[j], "rmax");
                coeff = self.pair_coeff.get(type_list[i], type_list[j], "coeff");

                self.update_pair_table(i, j, func, rmin, rmax, coeff);

    def set_from_file(self, a, b, filename):
        R""" Set a pair interaction from a file.

        Args:
            a (str): Name of type A in pair
            b (str): Name of type B in pair
            filename (str): Name of the file to read

        The provided file specifies V and F at equally spaced r values.

        Example::

            #r  V    F
            1.0 2.0 -3.0
            1.1 3.0 -4.0
            1.2 2.0 -3.0
            1.3 1.0 -2.0
            1.4 0.0 -1.0
            1.5 -1.0 0.0

        The first r value sets *rmin*, the last sets *rmax*. Any line with # as the first non-whitespace character is
        is treated as a comment. The *r* values must monotonically increase and be equally spaced. The table is read
        directly into the grid points used to evaluate :math:`F_{\mathrm{user}}(r)` and :math:`_{\mathrm{user}}(r)`.
        """
        hoomd.util.print_status_line();

        # open the file
        f = open(filename);

        r_table = [];
        V_table = [];
        F_table = [];

        # read in lines from the file
        for line in f.readlines():
            line = line.strip();

            # skip comment lines
            if line[0] == '#':
                continue;

            # split out the columns
            cols = line.split();
            values = [float(f) for f in cols];

            # validate the input
            if len(values) != 3:
                hoomd.context.msg.error("pair.table: file must have exactly 3 columns\n");
                raise RuntimeError("Error reading table file");

            # append to the tables
            r_table.append(values[0]);
            V_table.append(values[1]);
            F_table.append(values[2]);

        # validate input
        if self.width != len(r_table):
            hoomd.context.msg.error("pair.table: file must have exactly " + str(self.width) + " rows\n");
            raise RuntimeError("Error reading table file");

        # extract rmin and rmax
        rmin_table = r_table[0];
        rmax_table = r_table[-1];

        # check for even spacing
        dr = (rmax_table - rmin_table) / float(self.width-1);
        for i in range(0,self.width):
            r = rmin_table + dr * i;
            if math.fabs(r - r_table[i]) > 1e-3:
                hoomd.context.msg.error("pair.table: r must be monotonically increasing and evenly spaced\n");
                raise RuntimeError("Error reading table file");

        hoomd.util.quiet_status();
        self.pair_coeff.set(a, b, func=_table_eval, rmin=rmin_table, rmax=rmax_table, coeff=dict(V=V_table, F=F_table, width=self.width))
        hoomd.util.unquiet_status();

class morse(pair):
    R""" Morse pair potential.

    :py:class:`morse` specifies that a Morse pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{morse}}(r)  = & D_0 \left[ \exp \left(-2\alpha\left(r-r_0\right)\right) -2\exp \left(-\alpha\left(r-r_0\right)\right) \right] & r < r_{\mathrm{cut}} \\
                               = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`D_0` - *D0*, depth of the potential at its minimum (in energy units)
    - :math:`\alpha` - *alpha*, controls the width of the potential well (in units of 1/distance)
    - :math:`r_0` - *r0*, position of the minimum (in distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        morse = pair.morse(r_cut=3.0, nlist=nl)
        morse.pair_coeff.set('A', 'A', D0=1.0, alpha=3.0, r0=1.0)
        morse.pair_coeff.set('A', 'B', D0=1.0, alpha=3.0, r0=1.0, r_cut=3.0, r_on=2.0);
        morse.pair_coeff.set(['A', 'B'], ['C', 'D'], D0=1.0, alpha=3.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairMorse(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMorse;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairMorseGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMorseGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['D0', 'alpha', 'r0'];

    def process_coeff(self, coeff):
        D0 = coeff['D0'];
        alpha = coeff['alpha'];
        r0 = coeff['r0']

        return _hoomd.make_scalar4(D0, alpha, r0, 0.0);

class dpd(pair):
    R""" Dissipative Particle Dynamics.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        T (:py:mod:`hoomd.variant` or :py:obj:`float`): Temperature of thermostat (in energy units).
        seed (int): seed for the PRNG in the DPD thermostat.
        name (str): Name of the force instance.

    :py:class:`dpd` specifies that a DPD pair force should be applied between every
    non-excluded particle pair in the simulation, including an interaction potential,
    pairwise drag force, and pairwise random force. See `Groot and Warren 1997 <http://dx.doi.org/10.1063/1.474784>`_.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        F =   F_{\mathrm{C}}(r) + F_{\mathrm{R,ij}}(r_{ij}) +  F_{\mathrm{D,ij}}(v_{ij}) \\
        \end{eqnarray*}

    .. math::
        :nowrap:

        \begin{eqnarray*}
        F_{\mathrm{C}}(r) = & A \cdot  w(r_{ij}) \\
        F_{\mathrm{R, ij}}(r_{ij}) = & - \theta_{ij}\sqrt{3} \sqrt{\frac{2k_b\gamma T}{\Delta t}}\cdot w(r_{ij})  \\
        F_{\mathrm{D, ij}}(r_{ij}) = & - \gamma w^2(r_{ij})\left( \hat r_{ij} \circ v_{ij} \right)  \\
        \end{eqnarray*}

    .. math::
        :nowrap:

        \begin{eqnarray*}
        w(r_{ij}) = &\left( 1 - r/r_{\mathrm{cut}} \right)  & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    where :math:`\hat r_{ij}` is a normalized vector from particle i to particle j, :math:`v_{ij} = v_i - v_j`,
    and :math:`\theta_{ij}` is a uniformly distributed random number in the range [-1, 1].

    `C. L. Phillips et. al. 2011 <http://dx.doi.org/10.1016/j.jcp.2011.05.021>`_ describes the DPD implementation
    details in HOOMD-blue. Cite it if you utilize the DPD functionality in your work.

    :py:class:`dpd` does not implement and energy shift / smoothing modes due to the function of the force.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`A` - *A* (in force units)
    - :math:`\gamma` - *gamma* (in units of force/velocity)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    To use the DPD thermostat, an :py:class:`hoomd.md.integrate.nve` integrator must be applied to the system and
    the user must specify a temperature.  Use of the dpd thermostat pair force with other integrators will result
    in unphysical behavior. To use pair.dpd with a different conservative potential than :math:`F_C`,
    set A to zero and define the conservative pair potential separately.  Note that DPD thermostats
    are often defined in terms of :math:`\sigma` where :math:`\sigma = \sqrt{2k_b\gamma T}`.

    Example::

        nl = nlist.cell()
        dpd = pair.dpd(r_cut=1.0, nlist=nl, T=1.0)
        dpd.pair_coeff.set('A', 'A', A=25.0, gamma = 4.5)
        dpd.pair_coeff.set('A', 'B', A=40.0, gamma = 4.5)
        dpd.pair_coeff.set('B', 'B', A=25.0, gamma = 4.5)
        dpd.pair_coeff.set(['A', 'B'], ['C', 'D'], A=12.0, gamma = 1.2)
        dpd.set_params(T = 1.0)
        integrate.mode_standard(dt=0.02)
        integrate.nve(group=group.all())

    """
    def __init__(self, r_cut, nlist, T, seed=1, name=None):
        hoomd.util.print_status_line();

        # register the citation
        c = hoomd.cite.article(cite_key='phillips2011',
                         author=['C L Phillips', 'J A Anderson', 'S C Glotzer'],
                         title='Pseudo-random number generation for Brownian Dynamics and Dissipative Particle Dynamics simulations on GPU devices',
                         journal='Journal of Computational Physics',
                         volume=230,
                         number=19,
                         pages='7191--7201',
                         month='Aug',
                         year='2011',
                         doi='10.1016/j.jcp.2011.05.021',
                         feature='DPD')
        hoomd.cite._ensure_global_bib().add(c)

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairDPDThermoDPD(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPDThermoDPD;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairDPDThermoDPDGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPDThermoDPDGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['A', 'gamma'];

        # set the seed for dpd thermostat
        self.cpp_force.setSeed(seed);

        # set the temperature
        # setup the variant inputs
        T = hoomd.variant._setup_variant_input(T);
        self.cpp_force.setT(T.cpp_variant);

    def set_params(self, T=None):
        R""" Changes parameters.

        Args:
            T (:py:mod:`hoomd.variant` or :py:obj:`float`): Temperature of thermostat (in energy units).

        Example::

            dpd.set_params(T=2.0)
        """
        hoomd.util.print_status_line();
        self.check_initialization();

        # change the parameters
        if T is not None:
            # setup the variant inputs
            T = variant._setup_variant_input(T);
            self.cpp_force.setT(T.cpp_variant);

    def process_coeff(self, coeff):
        a = coeff['A'];
        gamma = coeff['gamma'];
        return _hoomd.make_scalar2(a, gamma);

class dpd_conservative(pair):
    R""" DPD Conservative pair force.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`dpd_conservative` specifies the conservative part of the DPD pair potential should be applied between
    every non-excluded particle pair in the simulation. No thermostat (e.g. Drag Force and Random Force) is applied,
    as is in :py:class:`dpd`.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{DPD-C}}(r)  = & A \cdot \left( r_{\mathrm{cut}} - r \right)
                               - \frac{1}{2} \cdot \frac{A}{r_{\mathrm{cut}}} \cdot \left(r_{\mathrm{cut}}^2 - r^2 \right)
                                      & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}


    :py:class:`dpd_conservative` does not implement and energy shift / smoothing modes due to the function of the force.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`A` - *A* (in force units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        dpdc = pair.dpd_conservative(r_cut=3.0, nlist=nl)
        dpdc.pair_coeff.set('A', 'A', A=1.0)
        dpdc.pair_coeff.set('A', 'B', A=2.0, r_cut = 1.0)
        dpdc.pair_coeff.set('B', 'B', A=1.0)
        dpdc.pair_coeff.set(['A', 'B'], ['C', 'D'], A=5.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # register the citation
        c = hoomd.cite.article(cite_key='phillips2011',
                         author=['C L Phillips', 'J A Anderson', 'S C Glotzer'],
                         title='Pseudo-random number generation for Brownian Dynamics and Dissipative Particle Dynamics simulations on GPU devices',
                         journal='Journal of Computational Physics',
                         volume=230,
                         number=19,
                         pages='7191--7201',
                         month='Aug',
                         year='2011',
                         doi='10.1016/j.jcp.2011.05.021',
                         feature='DPD')
        hoomd.cite._ensure_global_bib().add(c)

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairDPD(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPD;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairDPDGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPDGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['A'];


    def process_coeff(self, coeff):
        a = coeff['A'];
        gamma = 0;
        return _hoomd.make_scalar2(a, gamma);

    ## Not implemented for dpd_conservative
    #
    def set_params(self, coeff):
        raise RuntimeError('Not implemented for DPD Conservative');
        return;

class eam(force._force):
    R""" EAM pair potential.

    Args:
        file (str): Filename with potential tables in Alloy or FS format
        type (str): Type of file potential ('Alloy', 'FS')
        nlist (:py:mod:`hoomd.nlist`): Neighbor list (default of None automatically creates a global cell-list based neighbor list)

    :py:class:`eam` specifies that a EAM (embedded atom method) pair potential should be applied between every
    non-excluded particle pair in the simulation.

    No coefficients need to be set for :py:class:`eam`. All specifications, including the cutoff radius, form of the
    potential, etc. are read in from the specified file.

    Particle type names must match those referenced in the EAM potential file.

    Two file formats are supported: *Alloy* and *FS*. They are described in LAMMPS documentation
    (commands eam/alloy and eam/fs) here: http://lammps.sandia.gov/doc/pair_eam.html
    and are also described here: http://enpub.fulton.asu.edu/cms/potentials/submain/format.htm

    .. attention::
        EAM is **NOT** supported in MPI parallel simulations.

    .. danger::
        HOOMD-blue's EAM implementation is known to be broken.

    Example::

        nl = nlist.cell()
        eam = pair.eam(file='al1.mendelev.eam.fs', type='FS', nlist=nl)

    """
    def __init__(self, file, type, nlist):
        c = hoomd.cite.article(cite_key = 'morozov2011',
                         author=['I V Morozov','A M Kazennova','R G Bystryia','G E Normana','V V Pisareva','V V Stegailova'],
                         title = 'Molecular dynamics simulations of the relaxation processes in the condensed matter on GPUs',
                         journal = 'Computer Physics Communications',
                         volume = 182,
                         number = 9,
                         pages = '1974--1978',
                         year = '2011',
                         doi = '10.1016/j.cpc.2010.12.026',
                         feature = 'EAM')
        hoomd.cite._ensure_global_bib().add(c)

        hoomd.util.print_status_line();

        # Error out in MPI simulations
        if (_hoomd.is_MPI_available()):
            if hoomd.context.current.system_definition.getParticleData().getDomainDecomposition():
                hoomd.context.msg.error("pair.eam is not supported in multi-processor simulations.\n\n")
                raise RuntimeError("Error setting up pair potential.")

        # initialize the base class
        force._force.__init__(self);
        # Translate type
        if(type == 'Alloy'): type_of_file = 0;
        elif(type == 'FS'): type_of_file = 1;
        else: raise RuntimeError('Unknown EAM input file type');

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.EAMForceCompute(hoomd.context.current.system_definition, file, type_of_file);
        else:
            self.cpp_force = _md.EAMForceComputeGPU(hoomd.context.current.system_definition, file, type_of_file);

        #After load EAMForceCompute we know r_cut from EAM potential`s file. We need update neighbor list.
        r_cut_new = self.cpp_force.get_r_cut();
        self.nlist = nlist
        self.nlist.subscribe(lambda : r_cut_new)
        self.nlist.update_rcut()

        #Load neighbor list to compute.
        self.cpp_force.set_neighbor_list(self.nlist);
        if hoomd.context.exec_conf.isCUDAEnabled():
            self.nlist.setStorageMode(_md.NeighborList.storageMode.full);

        hoomd.context.msg.notice(2, "Set r_cut = " + str(r_cut_new) + " from potential`s file '" +  str(file) + "'.\n");

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);
        self.pair_coeff = coeff();

    def update_coeffs(self):
        # check that the pair coefficients are valid
        pass;

class dpdlj(pair):
    R""" Dissipative Particle Dynamics with a LJ conservative force

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        T (:py:mod:`hoomd.variant` or :py:obj:`float`): Temperature of thermostat (in energy units).
        seed (int): seed for the PRNG in the DPD thermostat.
        name (str): Name of the force instance.

    :py:class:`dpdlj` specifies that a DPD thermostat and a Lennard-Jones pair potential should be applied between
    every non-excluded particle pair in the simulation.

    `C. L. Phillips et. al. 2011 <http://dx.doi.org/10.1016/j.jcp.2011.05.021>`_ describes the DPD implementation
    details in HOOMD-blue. Cite it if you utilize the DPD functionality in your work.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        F =   F_{\mathrm{C}}(r) + F_{\mathrm{R,ij}}(r_{ij}) +  F_{\mathrm{D,ij}}(v_{ij}) \\
        \end{eqnarray*}

    .. math::
        :nowrap:

        \begin{eqnarray*}
        F_{\mathrm{C}}(r) = & \partial V_{\mathrm{LJ}} / \partial r \\
        F_{\mathrm{R, ij}}(r_{ij}) = & - \theta_{ij}\sqrt{3} \sqrt{\frac{2k_b\gamma T}{\Delta t}}\cdot w(r_{ij})  \\
        F_{\mathrm{D, ij}}(r_{ij}) = & - \gamma w^2(r_{ij})\left( \hat r_{ij} \circ v_{ij} \right)  \\
        \end{eqnarray*}

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{LJ}}(r)  = & 4 \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{12} -
                          \alpha \left( \frac{\sigma}{r} \right)^{6} \right] & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    .. math::
        :nowrap:

        \begin{eqnarray*}
        w(r_{ij}) = &\left( 1 - r/r_{\mathrm{cut}} \right)  & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    where :math:`\hat r_{ij}` is a normalized vector from particle i to particle j, :math:`v_{ij} = v_i - v_j`,
    and :math:`\theta_{ij}` is a uniformly distributed random number in the range [-1, 1].

    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`\alpha` - *alpha* (unitless)
      - *optional*: defaults to 1.0
    - :math:`\gamma` - *gamma* (in units of force/velocity)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    To use the DPD thermostat, an :py:class:`hoomd.md.integrate.nve` integrator must be applied to the system and
    the user must specify a temperature.  Use of the dpd thermostat pair force with other integrators will result
    in unphysical behavior.

    Example::

        nl = nlist.cell()
        dpdlj = pair.dpdlj(r_cut=2.5, nlist=nl, T=1.0)
        dpdlj.pair_coeff.set('A', 'A', epsilon=1.0, sigma = 1.0, gamma = 4.5)
        dpdlj.pair_coeff.set('A', 'B', epsilon=0.0, sigma = 1.0 gamma = 4.5)
        dpdlj.pair_coeff.set('B', 'B', epsilon=1.0, sigma = 1.0 gamma = 4.5, r_cut = 2.0**(1.0/6.0))
        dpdlj.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon = 3.0,sigma=1.0, gamma = 1.2)
        dpdlj.set_params(T = 1.0)
        integrate.mode_standard(dt=0.005)
        integrate.nve(group=group.all())

    """

    def __init__(self, r_cut, nlist, T, seed=1, name=None):
        hoomd.util.print_status_line();

        # register the citation
        c = hoomd.cite.article(cite_key='phillips2011',
                         author=['C L Phillips', 'J A Anderson', 'S C Glotzer'],
                         title='Pseudo-random number generation for Brownian Dynamics and Dissipative Particle Dynamics simulations on GPU devices',
                         journal='Journal of Computational Physics',
                         volume=230,
                         number=19,
                         pages='7191--7201',
                         month='Aug',
                         year='2011',
                         doi='10.1016/j.jcp.2011.05.021',
                         feature='DPD')
        hoomd.cite._ensure_global_bib().add(c)

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairDPDLJThermoDPD(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPDLJThermoDPD;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairDPDLJThermoDPDGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairDPDLJThermoDPDGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon','sigma', 'alpha', 'gamma'];
        self.pair_coeff.set_default_coeff('alpha', 1.0);


        # set the seed for dpdlj thermostat
        self.cpp_force.setSeed(seed);

        # set the temperature
        # setup the variant inputs
        T = variant._setup_variant_input(T);
        self.cpp_force.setT(T.cpp_variant);

    def set_params(self, T=None, mode=None):
        R""" Changes parameters.

        Args:
            T (:py:mod:`hoomd.variant` or :py:obj:`float`): Temperature (if set) (in energy units)
            mode (str): energy shift/smoothing mode (default noshift).

        Examples::

            dpdlj.set_params(T=variant.linear_interp(points = [(0, 1.0), (1e5, 2.0)]))
            dpdlj.set_params(T=2.0, mode="shift")

        """
        hoomd.util.print_status_line();
        self.check_initialization();

        # change the parameters
        if T is not None:
            # setup the variant inputs
            T = hoomd.variant._setup_variant_input(T);
            self.cpp_force.setT(T.cpp_variant);

        if mode is not None:
            if mode == "xplor":
                hoomd.context.msg.error("XPLOR is smoothing is not supported with pair.dpdlj\n");
                raise RuntimeError("Error changing parameters in pair force");

            #use the inherited set_params
            pair.set_params(self, mode=mode)

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        sigma = coeff['sigma'];
        gamma = coeff['gamma'];
        alpha = coeff['alpha'];

        lj1 = 4.0 * epsilon * math.pow(sigma, 12.0);
        lj2 = alpha * 4.0 * epsilon * math.pow(sigma, 6.0);
        return _hoomd.make_scalar4(lj1, lj2, gamma, 0.0);

class force_shifted_lj(pair):
    R""" Force-shifted Lennard-Jones pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`force_shifted_lj` specifies that a modified Lennard-Jones pair force should be applied between
    non-excluded particle pair in the simulation. The force differs from the one calculated by  :py:class:`lj`
    by the subtraction of the value of the force at :math:`r_{\mathrm{cut}}`, such that the force smoothly goes
    to zero at the cut-off. The potential is modified by a linear function. This potential can be used as a substitute
    for :py:class:`lj`, when the exact analytical form of the latter is not required but a smaller cut-off radius is
    desired for computational efficency. See `Toxvaerd et. al. 2011 <http://dx.doi.org/10.1063/1.3558787>`_
    for a discussion of this potential.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V(r)  = & 4 \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{12} -
                          \alpha \left( \frac{\sigma}{r} \right)^{6} \right] + \Delta V(r) & r < r_{\mathrm{cut}}\\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    .. math::

        \Delta V(r) = -(r - r_{\mathrm{cut}}) \frac{\partial V_{\mathrm{LJ}}}{\partial r}(r_{\mathrm{cut}})

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`\alpha` - *alpha* (unitless) - *optional*: defaults to 1.0
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        fslj = pair.force_shifted_lj(r_cut=1.5, nlist=nl)
        fslj.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairForceShiftedLJ(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairForceShiftedLJ;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairForceShiftedLJGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairForceShiftedLJGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'sigma', 'alpha'];
        self.pair_coeff.set_default_coeff('alpha', 1.0);

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        sigma = coeff['sigma'];
        alpha = coeff['alpha'];

        lj1 = 4.0 * epsilon * math.pow(sigma, 12.0);
        lj2 = alpha * 4.0 * epsilon * math.pow(sigma, 6.0);
        return _hoomd.make_scalar2(lj1, lj2);

class moliere(pair):
    R""" Moliere pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`moliere` specifies that a Moliere type pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{Moliere}}(r) = & \frac{Z_i Z_j e^2}{4 \pi \epsilon_0 r_{ij}} \left[ 0.35 \exp \left( -0.3 \frac{r_{ij}}{a_F} \right) + 0.55 \exp \left( -1.2 \frac{r_{ij}}{a_F} \right) + 0.10 \exp \left( -6.0 \frac{r_{ij}}{a_F} \right) \right] & r < r_{\mathrm{cut}} \\
                                = & 0 & r > r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`Z_i` - *Z_i* - Atomic number of species i (unitless)
    - :math:`Z_j` - *Z_j* - Atomic number of species j (unitless)
    - :math:`e` - *elementary_charge* - The elementary charge (in charge units)
    - :math:`a_0` - *a_0* - The Bohr radius (in distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        moliere = pair.moliere(r_cut = 3.0, nlist=nl)
        moliere.pair_coeff.set('A', 'B', Z_i = 54.0, Z_j = 7.0, elementary_charge = 1.0, a_0 = 1.0);

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairMoliere(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMoliere;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairMoliereGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMoliereGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficient options
        self.required_coeffs = ['Z_i', 'Z_j', 'elementary_charge', 'a_0'];
        self.pair_coeff.set_default_coeff('elementary_charge', 1.0);
        self.pair_coeff.set_default_coeff('a_0', 1.0);

    def process_coeff(self, coeff):
        Z_i = coeff['Z_i'];
        Z_j = coeff['Z_j'];
        elementary_charge = coeff['elementary_charge'];
        a_0 = coeff['a_0'];

        Zsq = Z_i * Z_j * elementary_charge * elementary_charge;
        if (not (Z_i == 0)) or (not (Z_j == 0)):
            aF = 0.8853 * a_0 / math.pow(math.sqrt(Z_i) + math.sqrt(Z_j), 2.0 / 3.0);
        else:
            aF = 1.0;
        return _hoomd.make_scalar2(Zsq, aF);

class zbl(pair):
    R""" ZBL pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`zbl` specifies that a Ziegler-Biersack-Littmark pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{ZBL}}(r) = & \frac{Z_i Z_j e^2}{4 \pi \epsilon_0 r_{ij}} \left[ 0.1818 \exp \left( -3.2 \frac{r_{ij}}{a_F} \right) + 0.5099 \exp \left( -0.9423 \frac{r_{ij}}{a_F} \right) + 0.2802 \exp \left( -0.4029 \frac{r_{ij}}{a_F} \right) + 0.02817 \exp \left( -0.2016 \frac{r_{ij}}{a_F} \right) \right], & r < r_{\mathrm{cut}} \\
                                = & 0, & r > r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`Z_i` - *Z_i* - Atomic number of species i (unitless)
    - :math:`Z_j` - *Z_j* - Atomic number of species j (unitless)
    - :math:`e` - *elementary_charge* - The elementary charge (in charge units)
    - :math:`a_0` - *a_0* - The Bohr radius (in distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        zbl = pair.zbl(r_cut = 3.0, nlist=nl)
        zbl.pair_coeff.set('A', 'B', Z_i = 54.0, Z_j = 7.0, elementary_charge = 1.0, a_0 = 1.0);

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairZBL(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairZBL;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairZBLGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairZBLGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficient options
        self.required_coeffs = ['Z_i', 'Z_j', 'elementary_charge', 'a_0'];
        self.pair_coeff.set_default_coeff('elementary_charge', 1.0);
        self.pair_coeff.set_default_coeff('a_0', 1.0);

    def process_coeff(self, coeff):
        Z_i = coeff['Z_i'];
        Z_j = coeff['Z_j'];
        elementary_charge = coeff['elementary_charge'];
        a_0 = coeff['a_0'];

        Zsq = Z_i * Z_j * elementary_charge * elementary_charge;
        if (not (Z_i == 0)) or (not (Z_j == 0)):
            aF = 0.88534 * a_0 / ( math.pow( Z_i, 0.23 ) + math.pow( Z_j, 0.23 ) );
        else:
            aF = 1.0;
        return _hoomd.make_scalar2(Zsq, aF);

class tersoff(pair):
    R""" Tersoff Potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`tersoff` specifies that the Tersoff three-body potential should be applied to every
    non-bonded particle pair in the simulation.  Despite the fact that the Tersoff potential accounts
    for the effects of third bodies, it is included in the pair potentials because the species of the
    third body is irrelevant. It can thus use type-pair parameters similar to those of the pair potentials.

    The Tersoff potential is a bond-order potential based on the Morse potential that accounts for the weakening of
    individual bonds with increasing coordination number. It does this by computing a modifier to the
    attractive term of the potential. The modifier contains the effects of third-bodies on the bond
    energies. The potential also includes a smoothing function around the cutoff. The smoothing function
    used in this work is exponential in nature as opposed to the sinusoid used by Tersoff. The exponential
    function provides continuity up (I believe) the second derivative.

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # this potential cannot handle a half neighbor list
        self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialTersoff(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialTersoff;
        else:
            self.cpp_force = _md.PotentialTersoffGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialTersoffGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficients
        self.required_coeffs = ['cutoff_thickness', 'C1', 'C2', 'lambda1', 'lambda2', 'dimer_r', 'n', 'gamma', 'lambda3', 'c', 'd', 'm', 'alpha']
        self.pair_coeff.set_default_coeff('cutoff_thickness', 0.2);
        self.pair_coeff.set_default_coeff('dimer_r', 1.5);
        self.pair_coeff.set_default_coeff('C1', 1.0);
        self.pair_coeff.set_default_coeff('C2', 1.0);
        self.pair_coeff.set_default_coeff('lambda1', 2.0);
        self.pair_coeff.set_default_coeff('lambda2', 1.0);
        self.pair_coeff.set_default_coeff('lambda3', 0.0);
        self.pair_coeff.set_default_coeff('n', 0.0);
        self.pair_coeff.set_default_coeff('m', 0.0);
        self.pair_coeff.set_default_coeff('c', 0.0);
        self.pair_coeff.set_default_coeff('d', 1.0);
        self.pair_coeff.set_default_coeff('gamma', 0.0);
        self.pair_coeff.set_default_coeff('alpha', 3.0);

    def process_coeff(self, coeff):
        cutoff_d = coeff['cutoff_thickness'];
        C1 = coeff['C1'];
        C2 = coeff['C2'];
        lambda1 = coeff['lambda1'];
        lambda2 = coeff['lambda2'];
        dimer_r = coeff['dimer_r'];
        n = coeff['n'];
        gamma = coeff['gamma'];
        lambda3 = coeff['lambda3'];
        c = coeff['c'];
        d = coeff['d'];
        m = coeff['m'];
        alpha = coeff['alpha'];

        gamman = math.pow(gamma, n);
        c2 = c * c;
        d2 = d * d;
        lambda3_cube = lambda3 * lambda3 * lambda3;

        tersoff_coeffs = _hoomd.make_scalar2(C1, C2);
        exp_consts = _hoomd.make_scalar2(lambda1, lambda2);
        ang_consts = _hoomd.make_scalar3(c2, d2, m);

        return _md.make_tersoff_params(cutoff_d, tersoff_coeffs, exp_consts, dimer_r, n, gamman, lambda3_cube, ang_consts, alpha);

class mie(pair):
    R""" Mie pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`mie` specifies that a Mie pair potential should be applied between every
    non-excluded particle pair in the simulation.

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{mie}}(r)  = & \left( \frac{n}{n-m} \right) {\left( \frac{n}{m} \right)}^{\frac{m}{n-m}} \varepsilon \left[ \left( \frac{\sigma}{r} \right)^{n} -
                          \left( \frac{\sigma}{r} \right)^{m} \right] & r < r_{\mathrm{cut}} \\
                            = & 0 & r \ge r_{\mathrm{cut}} \\
        \end{eqnarray*}

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\sigma` - *sigma* (in distance units)
    - :math:`n` - *n* (unitless)
    - :math:`m` - *m* (unitless)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}`- *r_on* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        mie = pair.mie(r_cut=3.0, nlist=nl)
        mie.pair_coeff.set('A', 'A', epsilon=1.0, sigma=1.0, n=12, m=6)
        mie.pair_coeff.set('A', 'B', epsilon=2.0, sigma=1.0, n=14, m=7, r_cut=3.0, r_on=2.0);
        mie.pair_coeff.set('B', 'B', epsilon=1.0, sigma=1.0, n=15.1, m=6.5, r_cut=2**(1.0/6.0), r_on=2.0);
        mie.pair_coeff.set(['A', 'B'], ['C', 'D'], epsilon=1.5, sigma=2.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairMie(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMie;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairMieGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairMieGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'sigma', 'n', 'm'];

    def process_coeff(self, coeff):
        epsilon = float(coeff['epsilon']);
        sigma = float(coeff['sigma']);
        n = float(coeff['n']);
        m = float(coeff['m']);

        mie1 = epsilon * math.pow(sigma, n) * (n/(n-m)) * math.pow(n/m,m/(n-m));
        mie2 = epsilon * math.pow(sigma, m) * (n/(n-m)) * math.pow(n/m,m/(n-m));
        mie3 = n
        mie4 = m
        return _hoomd.make_scalar4(mie1, mie2, mie3, mie4);

class ai_pair(pair):
    R""" Generic anisotropic pair potential.

    Users should not instantiate :py:class:`ai_pair` directly. It is a base class that
    provides common features to all anisotropic pair forces. Rather than repeating all of that documentation in a
    dozen different places, it is collected here.

    All anisotropic pair potential commands specify that a given potential energy, force and torque be computed
    on all non-excluded particle pairs in the system within a short range cutoff distance :math:`r_{\mathrm{cut}}`.
    The interaction energy, forces and torque depend on the inter-particle separation
    :math:`\vec r` and on the orientations :math:`\vec q_i`, :math:`q_j`, of the particles.
    """

    ## \internal
    # \brief Initialize the pair force
    # \details
    # The derived class must set
    #  - self.cpp_class (the pair class to instantiate)
    #  - self.required_coeffs (a list of the coeff names the derived class needs)
    #  - self.process_coeffs() (a method that takes in the coeffs and spits out a param struct to use in
    #       self.cpp_force.set_params())
    def __init__(self, r_cut, nlist, name=None):
        # initialize the base class
        force._force.__init__(self, name);

        self.global_r_cut = r_cut;

        # setup the coefficent matrix
        self.pair_coeff = coeff();
        self.pair_coeff.set_default_coeff('r_cut', self.global_r_cut);

        # setup the neighbor list
        self.nlist = nlist
        self.nlist.subscribe(lambda:self.get_rcut())
        self.nlist.update_rcut()

    def set_params(self, mode=None):
        R""" Set parameters controlling the way forces are computed.

        Args:
            mode (str): (if set) Set the mode with which potentials are handled at the cutoff

        valid values for mode are: "none" (the default) and "shift":

        - *none* - No shifting is performed and potentials are abruptly cut off
        - *shift* - A constant shift is applied to the entire potential so that it is 0 at the cutoff

        Examples::

            mypair.set_params(mode="shift")
            mypair.set_params(mode="no_shift")

        """
        hoomd.util.print_status_line();

        if mode is not None:
            if mode == "no_shift":
                self.cpp_force.setShiftMode(self.cpp_class.energyShiftMode.no_shift)
            elif mode == "shift":
                self.cpp_force.setShiftMode(self.cpp_class.energyShiftMode.shift)
            else:
                hoomd.context.msg.error("Invalid mode\n");
                raise RuntimeError("Error changing parameters in pair force");

    def update_coeffs(self):
        coeff_list = self.required_coeffs + ["r_cut"];
        # check that the pair coefficents are valid
        if not self.pair_coeff.verify(coeff_list):
            hoomd.context.msg.error("Not all pair coefficients are set\n");
            raise RuntimeError("Error updating pair coefficients");

        # set all the params
        ntypes = hoomd.context.current.system_definition.getParticleData().getNTypes();
        type_list = [];
        for i in range(0,ntypes):
            type_list.append(hoomd.context.current.system_definition.getParticleData().getNameByType(i));

        for i in range(0,ntypes):
            for j in range(i,ntypes):
                # build a dict of the coeffs to pass to process_coeff
                coeff_dict = {};
                for name in coeff_list:
                    coeff_dict[name] = self.pair_coeff.get(type_list[i], type_list[j], name);

                param = self.process_coeff(coeff_dict);
                self.cpp_force.setParams(i, j, param);
                self.cpp_force.setRcut(i, j, coeff_dict['r_cut']);

class gb(ai_pair):
    R""" Gay-Berne anisotropic pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`gb` computes the Gay-Berne potential between anisotropic particles.

    This version of the Gay-Berne potential supports identical pairs of uniaxial ellipsoids,
    with orientation-independent energy-well depth.

    The interaction energy for this anisotropic pair potential is
    (`Allen et. al. 2006 <http://dx.doi.org/10.1080/00268970601075238>`_):

    .. math::
        :nowrap:

        \begin{eqnarray*}
        V_{\mathrm{GB}}(\vec r, \vec e_i, \vec e_j)  = & 4 \varepsilon \left[ \zeta^{-12} -
                              \zeta^{-6} \right] & \zeta < \zeta_{\mathrm{cut}} \\
                            = & 0 & \zeta \ge \zeta_{\mathrm{cut}} \\
        \end{eqnarray*}

    .. math::

        \zeta = \left(\frac{r-\sigma+\sigma_{\mathrm{min}}}{\sigma_{\mathrm{min}}}\right)

        \sigma^{-2} = \frac{1}{2} \hat{\vec{r}}\cdot\vec{H^{-1}}\cdot\hat{\vec{r}}

        \vec{H} = 2 \ell_\perp^2 \vec{1} + (\ell_\parallel^2 - \ell_\perp^2) (\vec{e_i} \otimes \vec{e_i} + \vec{e_j} \otimes \vec{e_j})

    with :math:`\sigma_{\mathrm{min}} = 2 \min(\ell_\perp, \ell_\parallel)`.

    The cut-off parameter :math:`r_{\mathrm{cut}}` is defined for two particles oriented parallel along
    the **long** axis, i.e.
    :math:`\zeta_{\mathrm{cut}} = \left(\frac{r-\sigma_{\mathrm{max}} + \sigma_{\mathrm{min}}}{\sigma_{\mathrm{min}}}\right)`
    where :math:`\sigma_{\mathrm{max}} = 2 \max(\ell_\perp, \ell_\parallel)` .

    The quantities :math:`\ell_\parallel` and :math:`\ell_\perp` denote the semi-axis lengths parallel
    and perpendicular to particle orientation.

    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in energy units)
    - :math:`\ell_\perp` - *lperp* (in distance units)
    - :math:`\ell_\parallel` - *lpar* (in distance units)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in distance units)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        gb = pair.gb(r_cut=2.5, nlist=nl)
        gb.pair_coeff.set('A', 'A', epsilon=1.0, lperp=0.45, lpar=0.5)
        gb.pair_coeff.set('A', 'B', epsilon=2.0, lperp=0.45, lpar=0.5, r_cut=2**(1.0/6.0));

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        ai_pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.AnisoPotentialPairGB(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.AnisoPotentialPairGB;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.AnisoPotentialPairGBGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.AnisoPotentialPairGBGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'lperp', 'lpar'];

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        lperp = coeff['lperp'];
        lpar = coeff['lpar'];

        return _hoomd.make_scalar3(epsilon, lperp, lpar);

class dipole(ai_pair):
    R""" Screened dipole-dipole interactions.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`dipole` computes the (screened) interaction between pairs of
    particles with dipoles and electrostatic charges. The total energy
    computed is:

    .. math::

        U_{dipole} = U_{dd} + U_{de} + U_{ee}

        U_{dd} = A e^{-\kappa r} \left(\frac{\vec{\mu_i}\cdot\vec{\mu_j}}{r^3} - 3\frac{(\vec{\mu_i}\cdot \vec{r_{ji}})(\vec{\mu_j}\cdot \vec{r_{ji}})}{r^5}\right)

        U_{de} = A e^{-\kappa r} \left(\frac{(\vec{\mu_j}\cdot \vec{r_{ji}})q_i}{r^3} - \frac{(\vec{\mu_i}\cdot \vec{r_{ji}})q_j}{r^3}\right)

        U_{ee} = A e^{-\kappa r} \frac{q_i q_j}{r}

    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - mu - magnitude of :math:`\vec{\mu} = \mu (1, 0, 0)` in the particle local reference frame
    - A - electrostatic energy scale :math:`A` (default value 1.0)
    - kappa - inverse screening length :math:`\kappa`

    Example::

        # A/A interact only with screened electrostatics
        dipole.pair_coeff.set('A', 'A', mu=0.0, A=1.0, kappa=1.0)
        dipole.pair_coeff.set('A', 'B', mu=0.5, kappa=1.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        ## tell the base class how we operate

        # initialize the base class
        ai_pair.__init__(self, r_cut, nlist, name);

        ## create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.AnisoPotentialPairDipole(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.AnisoPotentialPairDipole;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.AnisoPotentialPairDipoleGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.AnisoPotentialPairDipoleGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        ## setup the coefficent options
        self.required_coeffs = ['mu', 'A', 'kappa'];

        self.pair_coeff.set_default_coeff('A', 1.0)

    def process_coeff(self, coeff):
        mu = float(coeff['mu']);
        A = float(coeff['A']);
        kappa = float(coeff['kappa']);

        params = _hoomd.make_scalar3(mu, A, kappa)

        return params

class reaction_field(pair):
    R""" Onsager reaction field pair potential.

    Args:
        r_cut (float): Default cutoff radius (in distance units).
        nlist (:py:mod:`hoomd.md.nlist`): Neighbor list
        name (str): Name of the force instance.

    :py:class:`reaction_field` specifies that an Onsager reaction field pair potential should be applied between every
    non-excluded particle pair in the simulation.

    Reaction field electrostatics is an approximation to the screened electrostatic interaction,
    which assumes that the medium can be treated as an electrostatic continuum of dielectric
    constant :math:`\epsilon_{RF}` outside the cutoff sphere of radius :math:`r_{\mathrm{cut}}`.
    See: `Barker et. al. 1973 <http://dx.doi.org/10.1080/00268977300102101>`_.

    .. math::

       V_{\mathrm{RF}}(r) = \varepsilon \left[ \frac{1}{r} +
           \frac{(\epsilon_{RF}-1) r^2}{(2 \epsilon_{RF} + 1) r_c^3} \right]

    The reaction field potential does not require charge or diameter to be set. Two parameters,
    :math:`\varepsilon` and :math:`\epsilon_{RF}` are needed. If :math:`epsilon_{RF}` is specified as zero,
    it will represent infinity.

    See :py:class:`pair` for details on how forces are calculated and the available energy shifting and smoothing modes.
    Use :py:meth:`pair_coeff.set <coeff.set>` to set potential coefficients.

    The following coefficients must be set per unique pair of particle types:

    - :math:`\varepsilon` - *epsilon* (in units of energy*distance)
    - :math:`\epsilon_{RF}` - *eps_rf* (dimensionless)
    - :math:`r_{\mathrm{cut}}` - *r_cut* (in units of distance)
      - *optional*: defaults to the global r_cut specified in the pair command
    - :math:`r_{\mathrm{on}}` - *r_on* (in units of distance)
      - *optional*: defaults to the global r_cut specified in the pair command

    Example::

        nl = nlist.cell()
        reaction_field = pair.reaction_field(r_cut=3.0, nlist=nl)
        reaction_field.pair_coeff.set('A', 'A', epsilon=1.0, eps_rf=1.0)
        reaction_field.pair_coeff.set('A', 'B', epsilon=-1.0, eps_rf=0.0)
        reaction_field.pair_coeff.set('B', 'B', epsilon=1.0, eps_rf=0.0)

    """
    def __init__(self, r_cut, nlist, name=None):
        hoomd.util.print_status_line();

        # tell the base class how we operate

        # initialize the base class
        pair.__init__(self, r_cut, nlist, name);

        # create the c++ mirror class
        if not hoomd.context.exec_conf.isCUDAEnabled():
            self.cpp_force = _md.PotentialPairReactionField(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairReactionField;
        else:
            self.nlist.cpp_nlist.setStorageMode(_md.NeighborList.storageMode.full);
            self.cpp_force = _md.PotentialPairReactionFieldGPU(hoomd.context.current.system_definition, self.nlist.cpp_nlist, self.name);
            self.cpp_class = _md.PotentialPairReactionFieldGPU;

        hoomd.context.current.system.addCompute(self.cpp_force, self.force_name);

        # setup the coefficent options
        self.required_coeffs = ['epsilon', 'eps_rf'];

    def process_coeff(self, coeff):
        epsilon = coeff['epsilon'];
        eps_rf = coeff['eps_rf'];

        return _hoomd.make_scalar2(epsilon, eps_rf);