! -----------------------------------------------------------------------------
! BSD 3-Clause License
!
! Copyright (c) 2017, Science and Technology Facilities Council
! All rights reserved.
!
! Redistribution and use in source and binary forms, with or without
! modification, are permitted provided that the following conditions are met:
!
! * Redistributions of source code must retain the above copyright notice, this
!   list of conditions and the following disclaimer.
!
! * Redistributions in binary form must reproduce the above copyright notice,
!   this list of conditions and the following disclaimer in the documentation
!   and/or other materials provided with the distribution.
!
! * Neither the name of the copyright holder nor the names of its
!   contributors may be used to endorse or promote products derived from
!   this software without specific prior written permission.
!
! THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
! AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
! IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
! DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
! FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
! DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
! SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
! CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
! OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
! OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
! -----------------------------------------------------------------------------
! Authors: R. W. Ford and A. R. Porter, STFC Daresbury Lab

module testkern_any_space_3_mod
  use argument_mod
  use kernel_mod
  use constants_mod
  ! test for any_space producing correct code where there are 1) different
  ! spaces for the to and from parts of an operator, 2) no other arguments

type, public, extends(kernel_type) ::testkern_any_space_3_type
  type(arg_type) :: meta_args(1) = (/                                  &
       arg_type(GH_OPERATOR, GH_INC, ANY_SPACE_1, ANY_SPACE_2)        &
       /)
  integer :: iterates_over = CELLS
contains
  procedure, public, nopass :: testkern_any_space_3_code
end type testkern_any_space_3_type
!
contains
  subroutine testkern_any_space_3_code(cell, nlayers, ncell_3d, local_stencil, &
       ndf_any_space_1_op, ndf_any_space_2_op)
    implicit none
    integer :: cell, nlayers, ncell_3d, ndf_any_space_1_op, &
         ndf_any_space_2_op
    real(kind=r_def), dimension(:,:,:) :: local_stencil
  end subroutine testkern_any_space_3_code
!
end module testkern_any_space_3_mod
