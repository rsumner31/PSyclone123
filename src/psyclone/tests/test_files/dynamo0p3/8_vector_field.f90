!-------------------------------------------------------------------------------
! (c) The copyright relating to this work is owned jointly by the Crown,
! Met Office and NERC 2015.
! However, it has been created with the help of the GungHo Consortium,
! whose members are identified at https://puma.nerc.ac.uk/trac/GungHo/wiki
!-------------------------------------------------------------------------------
! Author R. Ford STFC Daresbury Lab

program vector_field

  ! Description: vector field passed as an argument
  use testkern_chi, only: testkern_chi_type
  use inf,      only: field_type
  implicit none
  type(field_type) :: f1, chi(3), f2

  call invoke(                        &
       testkern_chi_type(f1,chi,f2)   &
       )

end program vector_field
