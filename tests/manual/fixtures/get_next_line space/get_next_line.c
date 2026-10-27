#include "get_next_line.h"
char *get_next_line(int fd) { char *s=malloc(1000000); int n=0; char c; if (!s) return 0; while (n<999998 && read(fd,&c,1)==1) {s[n++]=c; if(c==10) break;} s[n]=0; if(!n){free(s); return 0;} return s;}
