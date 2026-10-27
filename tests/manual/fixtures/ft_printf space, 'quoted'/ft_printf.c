#include <stdarg.h>
#include <stdio.h>
int ft_printf(const char *s, ...) { va_list ap; va_start(ap, s); int n=vprintf(s, ap); va_end(ap); return n; }
