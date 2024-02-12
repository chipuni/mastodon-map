connected(X, Y) :- peer(X, Y), peer(Y, X), X \= Y.
nconnected(N, X, Y) :- N = 1, connected(X, Y);
		       N > 1, N2 is N - 1, dif(X, Y), connected(X, Z), nconnected(N2, Z, Y), \+ nconnected(N2, X, Y).
