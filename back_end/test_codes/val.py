# formatted_licenses = ["**Apache-2.0**",'BSD-3-Clause' ]

# licenses_str = ", ".join(formatted_licenses)

# print(licenses_str)

str1 = 'GPL-3.0+ with GCC-exception-3.1, Apache-2.0 WITH LLVM-exception, Permission Notice , Spencer-94, LGPL-2.1+ with GCC-exception, Public-Domain, Permission Notice, SunPro, Dual-license, ISC, NCSA, BSD-3-Clause, MIT, BSD-2-Clause, BSL-1.0, LGPL-2.1-or-later, LGPL-2.0-or-later'

strlist = str1.split(',')

length = len(strlist)

list1 = ['Apache-2.0 WITH LLVM-exception', 'Permission Notice ', 'Spencer-94', 'LGPL-2.1+ with GCC-exception', 'Public-Domain', 'Permission Notice', 'GPL-3.0+ with GCC-exception-3.1', 'SunPro', 'Dual-license', 'ISC', 'NCSA', 'BSD-3-Clause', 'MIT', 'BSD-2-Clause', 'BSL-1.0', 'LGPL-2.1-or-later', 'LGPL-2.0-or-later']

lenght1 = len(list1)

print(f'original length{length}, now it is{lenght1}')