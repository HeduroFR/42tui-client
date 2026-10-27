NAME = libftprintf.a
all: $(NAME)
$(NAME): ft_printf.c
	cc -Wall -Wextra -Werror -c ft_printf.c
	ar rcs $(NAME) ft_printf.o
clean:
	rm -f ft_printf.o
fclean: clean
	rm -f $(NAME)
re: fclean all
bonus: all
.PHONY: all clean fclean re bonus
