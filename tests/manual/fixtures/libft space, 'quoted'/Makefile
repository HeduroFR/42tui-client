NAME = libft.a
all: $(NAME)
$(NAME): ft_isalpha.c
	cc -Wall -Wextra -Werror -c ft_isalpha.c
	ar rcs $(NAME) ft_isalpha.o
clean:
	rm -f ft_isalpha.o
fclean: clean
	rm -f $(NAME)
re: fclean all
bonus: all
.PHONY: all clean fclean re bonus
