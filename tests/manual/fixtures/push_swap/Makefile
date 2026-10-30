NAME = push_swap
all: $(NAME)
$(NAME): push_swap.c
	$(CC) -Wall -Wextra -Werror push_swap.c -o $(NAME)
clean:
	rm -f *.o
fclean: clean
	rm -f $(NAME)
re: fclean all
.PHONY: all clean fclean re
