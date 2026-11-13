from __future__ import annotations

import copy
from typing import Dict, List, Tuple

N = 0
M = 0
lastfalse = {}
rr = []
solution = {}
_log_level = "brief"
_log_suspend = 0


def _log_edge(i, j, x, y, v, debug=""):
    return

def query(i, j, x, y, connections):
    if i < 0 or i > N or j < 0 or j > M or x < 0 or x > N or y < 0 or y > M:
        return 2
    if (i, j) in connections and (x, y) in connections[(i, j)]:
        return connections[(i, j)][(x, y)]
    return 0


def getv(i, j, connections):
    x = [
        query(i, j, i + 1, j, connections),
        query(i, j, i, j + 1, connections),
        query(i, j, i - 1, j, connections),
        query(i, j, i, j - 1, connections),
    ]
    x0 = x1 = x2 = 0
    for a in x:
        if a == 0:
            x0 += 1
        if a == 1:
            x1 += 1
        if a == 2:
            x2 += 1
    return x0, x1, x2


def get8m(i, j):
    return [
        (i, j, i - 1, j),
        (i, j, i, j - 1),
        (i, j + 1, i - 1, j + 1),
        (i, j + 1, i, j + 2),
        (i + 1, j, i + 1, j - 1),
        (i + 1, j, i + 2, j),
        (i + 1, j + 1, i + 1, j + 2),
        (i + 1, j + 1, i + 2, j + 1),
    ]


def getvx(i, j, connections):
    return [
        query(i, j, i + 1, j, connections),
        query(i, j, i, j + 1, connections),
        query(i, j, i - 1, j, connections),
        query(i, j, i, j - 1, connections),
    ]


def getm(i, j, connections):
    x = [
        query(i, j, i + 1, j, connections),
        query(i, j + 1, i + 1, j + 1, connections),
        query(i + 1, j, i + 1, j + 1, connections),
        query(i, j, i, j + 1, connections),
    ]
    x0 = x1 = x2 = 0
    for a in x:
        if a == 0:
            x0 += 1
        if a == 1:
            x1 += 1
        if a == 2:
            x2 += 1
    return x0, x1, x2


def miji(i, j, x, y, connections):
    global lastfalse
    n = 0
    if (i, j, x, y) in lastfalse:
        n = lastfalse[(i, j, x, y)] * 1000
    for a in range(i - 2, i + 2):
        for b in range(j - 2, j + 2):
            if query(a, b, a + 1, b, connections) > 0:
                n += 1
            if query(a, b, a, b + 1, connections) > 0:
                n += 1
    if query(i + 1, j + 2, i + 2, j + 2, connections) > 0:
        n += 1
    if query(i + 2, j + 1, i + 2, j + 2, connections) > 0:
        n += 1
    return n


def getzero(matrix, connections):
    z = []
    for i in range(N):
        for j in range(M):
            if (i, j) not in connections:
                z.append((i, j, i + 1, j))
                z.append((i, j, i, j + 1))
            else:
                if (i + 1, j) not in connections[(i, j)]:
                    z.append((i, j, i + 1, j))
                if (i, j + 1) not in connections[(i, j)]:
                    z.append((i, j, i, j + 1))
    z = sorted(z, key=lambda x: -miji(x[0], x[1], x[2], x[3], connections) - miji(x[2], x[3], x[0], x[1], connections))
    return z


def find_couple_same(matrix, connections):
    couple = {}
    for i in range(N + 1):
        for j in range(M + 1):
            x0, x1, x2 = getv(i, j, connections)
            if x0 == 2 and x2 == 2:
                if query(i, j, i + 1, j, connections) == 0 and query(i, j, i, j + 1, connections) == 0:
                    couple.setdefault((i, j), []).append(2)
                elif query(i, j, i - 1, j, connections) == 0 and query(i, j, i, j + 1, connections) == 0:
                    couple.setdefault((i, j), []).append(1)
                elif query(i, j, i - 1, j, connections) == 0 and query(i, j, i, j - 1, connections) == 0:
                    couple.setdefault((i, j), []).append(0)
                elif query(i, j, i + 1, j, connections) == 0 and query(i, j, i, j - 1, connections) == 0:
                    couple.setdefault((i, j), []).append(3)
                else:
                    couple.setdefault((i, j), []).append(4)
    return couple


def find_couple(matrix, connections):
    couple = {}
    for i in range(N):
        for j in range(M):
            x0, x1, x2 = getm(i, j, connections)
            if x0 == 2 and matrix[i][j] - x1 == 1 and matrix[i][j] != 4:
                if query(i, j, i + 1, j, connections) == 0 and query(i, j, i, j + 1, connections) == 0:
                    couple.setdefault((i, j), []).append(2)
                if query(i, j + 1, i, j, connections) == 0 and query(i, j + 1, i + 1, j + 1, connections) == 0:
                    couple.setdefault((i, j + 1), []).append(3)
                if query(i + 1, j, i, j, connections) == 0 and query(i + 1, j, i + 1, j + 1, connections) == 0:
                    couple.setdefault((i + 1, j), []).append(1)
                if query(i + 1, j + 1, i, j + 1, connections) == 0 and query(i + 1, j + 1, i + 1, j, connections) == 0:
                    couple.setdefault((i + 1, j + 1), []).append(0)
            x = getvx(i, j, connections)
            if getv(i, j, connections)[1] == 1 and getv(i, j, connections)[2] == 1 and ((x[0] == x[2] and x[0] == 0) or (x[1] == x[3] and x[1] == 0)):
                couple.setdefault((i, j), []).append(4)

    for i in range(N + 1):
        for j in range(M + 1):
            x0, x1, x2 = getv(i, j, connections)
            if x0 == 2 and x1 == 1:
                if query(i, j, i + 1, j, connections) == 0 and query(i, j, i, j + 1, connections) == 0:
                    couple.setdefault((i, j), []).append(2)
                if query(i, j, i - 1, j, connections) == 0 and query(i, j, i, j + 1, connections) == 0:
                    couple.setdefault((i, j), []).append(1)
                if query(i, j, i - 1, j, connections) == 0 and query(i, j, i, j - 1, connections) == 0:
                    couple.setdefault((i, j), []).append(0)
                if query(i, j, i + 1, j, connections) == 0 and query(i, j, i, j - 1, connections) == 0:
                    couple.setdefault((i, j), []).append(3)

    lastcouple = -1
    lcouple = len(couple)
    while lcouple != lastcouple:
        lastcouple = lcouple
        k = list(couple.keys())
        for (i, j) in k:
            if 0 in couple[(i, j)]:
                if i < N and j < M and matrix[i][j] == 2:
                    couple.setdefault((i + 1, j + 1), []).append(0)
                    couple[(i, j)].append(2)
                if i > 0 and j > 0 and matrix[i - 1][j - 1] == 2:
                    couple.setdefault((i - 1, j - 1), []).append(2)

            if 1 in couple[(i, j)]:
                if i < N and j > 0 and matrix[i][j - 1] == 2:
                    couple.setdefault((i + 1, j - 1), []).append(1)
                    couple[(i, j)].append(3)
                if i > 0 and j < M and matrix[i - 1][j] == 2:
                    couple.setdefault((i - 1, j + 1), []).append(3)

            if 2 in couple[(i, j)]:
                if i > 0 and j > 0 and matrix[i - 1][j - 1] == 2:
                    couple.setdefault((i - 1, j - 1), []).append(2)
                    couple[(i, j)].append(0)
                if i < N and j < M and matrix[i][j] == 2:
                    couple.setdefault((i + 1, j + 1), []).append(0)

            if 3 in couple[(i, j)]:
                if i > 0 and j < M and matrix[i - 1][j] == 2:
                    couple.setdefault((i - 1, j + 1), []).append(3)
                    couple[(i, j)].append(1)
                if i < N and j > 0 and matrix[i][j - 1] == 2:
                    couple.setdefault((i + 1, j - 1), []).append(1)
        lcouple = len(couple)
    return couple


def quan(G):
    num = 0
    for i in G:
        if len(G[i]) > 1:
            num += 1
    return num


def Set(i, j, x, y, connections, v, G, Gid, debug=""):
    if i < 0 or i > N or j < 0 or j > M or x < 0 or x > N or y < 0 or y > M:
        return
    if v == 1 and quan(G) > 1 and Gid[(i, j)] == Gid[(x, y)]:
        return
    created = False
    if (i, j) not in connections:
        connections[(i, j)] = {}
    if (x, y) not in connections[(i, j)]:
        connections[(i, j)][(x, y)] = v
        created = True
        if v == 1:
            gij = Gid[(i, j)]
            gxy = Gid[(x, y)]
            for (a, b) in G[gxy]:
                Gid[(a, b)] = gij
            if gxy != gij:
                G[gij] = G[gxy] + G[gij]
                del G[gxy]

    if (x, y) not in connections:
        connections[(x, y)] = {}
    if (i, j) not in connections[(x, y)]:
        connections[(x, y)][(i, j)] = v
    if created:
        _log_edge(i, j, x, y, v, debug=debug)


def Setcouple(i, j, x1, y1, x2, y2, connections, v, G, Gid, debug=""):
    if i < 0 or i > N or j < 0 or j > M or x1 < 0 or x1 > N or y1 < 0 or y1 > M or x2 < 0 or x2 > N or y2 < 0 or y2 > M:
        return
    if (i, j) not in connections:
        connections[(i, j)] = {}
    if (x1, y1) not in connections[(i, j)]:
        connections[(i, j)][(x1, y1)] = v
    if (x2, y2) not in connections[(i, j)]:
        connections[(i, j)][(x2, y2)] = v
    if (x1, y1) not in connections:
        connections[(x1, y1)] = {}
    if (i, j) not in connections[(x1, y1)]:
        connections[(x1, y1)][(i, j)] = v
    if (x2, y2) not in connections:
        connections[(x2, y2)] = {}
    if (i, j) not in connections[(x2, y2)]:
        connections[(x2, y2)][(i, j)] = v

    gij = Gid[(i, j, x1, y1)]
    gxy = Gid[(i, j, x2, y2)]
    if gxy != gij:
        for (a, b, x, y) in G[gxy]:
            Gid[(a, b, x, y)] = gij
        G[gij] = G[gxy] + G[gij]
        del G[gxy]


def isvalid(matrix, connections, G, Gid):
    for i in range(N + 1):
        for j in range(M + 1):
            x0, x1, x2 = getv(i, j, connections)
            if (x1 == 3 and x2 == 1) or (x1 == 1 and x2 == 3) or x1 > 2:
                return 0
    for i in range(N):
        for j in range(M):
            x0, x1, x2 = getm(i, j, connections)
            if matrix[i][j] != 4:
                if x1 > matrix[i][j] or x2 > 4 - matrix[i][j]:
                    return 0
    return 1


def solve_core(matrix, connections, G, Gid, deepth, apply_search=False, extra=None):
    if extra is not None:
        i, j, x, y, v = extra
        Set(i, j, x, y, connections, v, G, Gid)
    l = 0
    lastl = -1
    while l != lastl:
        c = find_couple(matrix, connections)
        lastl = l

        for i in range(N):
            for j in range(M):
                p = get8m(i, j)
                xx = [query(a, b, c_, d_, connections) for (a, b, c_, d_) in p]
                xn = [0, 0, 0]
                for a in xx:
                    xn[a] += 1
                if xn[0] == 1:
                    idx = xx.index(0)
                    i1, j1, i2, j2 = p[idx]
                    if xn[1] % 2 == 1:
                        Set(i1, j1, i2, j2, connections, 1, G, Gid)
                    else:
                        Set(i1, j1, i2, j2, connections, 2, G, Gid)

                if matrix[i][j] != 4:
                    x0, x1, x2 = getm(i, j, connections)
                    if x2 == 4 - matrix[i][j]:
                        Set(i, j, i + 1, j, connections, 1, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                        Set(i, j, i, j + 1, connections, 1, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)
                    if x1 == matrix[i][j]:
                        Set(i, j, i + 1, j, connections, 2, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)
                        Set(i, j, i, j + 1, connections, 2, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)

                if matrix[i][j] == 1:
                    x = getvx(i, j, connections)
                    if x[2] == 2 and x[3] == 2:
                        Set(i, j, i + 1, j, connections, 2, G, Gid)
                        Set(i, j, i, j + 1, connections, 2, G, Gid)
                    if (x[2] == 2 and x[3] == 1) or (x[2] == 1 and x[3] == 2) or ((i, j) in c and 0 in c[(i, j)]):
                        Set(i + 1, j + 1, i + 1, j, connections, 2, G, Gid)
                        Set(i + 1, j + 1, i, j + 1, connections, 2, G, Gid)

                    x = getvx(i, j + 1, connections)
                    if x[2] == 2 and x[1] == 2:
                        Set(i, j + 1, i, j, connections, 2, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)
                    if (x[2] == 1 and x[1] == 2) or (x[2] == 2 and x[1] == 1) or ((i, j + 1) in c and 1 in c[(i, j + 1)]):
                        Set(i + 1, j, i, j, connections, 2, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)

                    x = getvx(i + 1, j, connections)
                    if x[0] == 2 and x[3] == 2:
                        Set(i + 1, j, i, j, connections, 2, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)
                    if (x[0] == 1 and x[3] == 2) or (x[0] == 2 and x[3] == 1) or ((i + 1, j) in c and 3 in c[(i + 1, j)]):
                        Set(i, j + 1, i, j, connections, 2, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)

                    x = getvx(i + 1, j + 1, connections)
                    if x[0] == 2 and x[1] == 2:
                        Set(i + 1, j + 1, i + 1, j, connections, 2, G, Gid)
                        Set(i + 1, j + 1, i, j + 1, connections, 2, G, Gid)
                    if (x[0] == 2 and x[1] == 1) or (x[0] == 1 and x[1] == 2) or ((i + 1, j + 1) in c and 2 in c[(i + 1, j + 1)]):
                        Set(i, j, i + 1, j, connections, 2, G, Gid)
                        Set(i, j, i, j + 1, connections, 2, G, Gid)

                if matrix[i][j] == 3:
                    x = getvx(i, j, connections)
                    if x[2] == 2 and x[3] == 2:
                        Set(i, j, i + 1, j, connections, 1, G, Gid)
                        Set(i, j, i, j + 1, connections, 1, G, Gid)
                    if (x[3] == 1) or (x[2] == 1) or ((i, j) in c and 0 in c[(i, j)]):
                        Set(i + 1, j + 1, i + 1, j, connections, 1, G, Gid)
                        Set(i + 1, j + 1, i, j + 1, connections, 1, G, Gid)

                    x = getvx(i, j + 1, connections)
                    if x[2] == 2 and x[1] == 2:
                        Set(i, j + 1, i, j, connections, 1, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)
                    if (x[2] == 1) or (x[1] == 1) or ((i, j + 1) in c and 1 in c[(i, j + 1)]):
                        Set(i + 1, j, i, j, connections, 1, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)

                    x = getvx(i + 1, j, connections)
                    if x[0] == 2 and x[3] == 2:
                        Set(i + 1, j, i, j, connections, 1, G, Gid)
                        Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                    if (x[0] == 1) or (x[3] == 1) or ((i + 1, j) in c and 3 in c[(i + 1, j)]):
                        Set(i, j + 1, i, j, connections, 1, G, Gid)
                        Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)

                    x = getvx(i + 1, j + 1, connections)
                    if x[0] == 2 and x[1] == 2:
                        Set(i + 1, j + 1, i + 1, j, connections, 1, G, Gid)
                        Set(i + 1, j + 1, i, j + 1, connections, 1, G, Gid)
                    if (x[1] == 1) or (x[0] == 1) or ((i + 1, j + 1) in c and 2 in c[(i + 1, j + 1)]):
                        Set(i, j, i + 1, j, connections, 1, G, Gid)
                        Set(i, j, i, j + 1, connections, 1, G, Gid)

                if matrix[i][j] == 2:
                    x = getvx(i, j, connections)
                    if x[2] == 2 and x[3] == 2:
                        if query(i + 1, j + 1, i + 1, j, connections) == 1 or query(i + 1, j + 1, i, j + 1, connections) == 1:
                            Set(i, j, i + 1, j, connections, 2, G, Gid)
                            Set(i, j, i, j + 1, connections, 2, G, Gid)
                        if query(i + 1, j + 1, i + 1, j, connections) == 2 or query(i + 1, j + 1, i, j + 1, connections) == 2:
                            Set(i, j, i + 1, j, connections, 1, G, Gid)
                            Set(i, j, i, j + 1, connections, 1, G, Gid)
                    if (x[2] == 2 and x[3] == 1) or (x[2] == 1 and x[3] == 2) or ((i, j) in c and 0 in c[(i, j)]):
                        if query(i + 1, j + 1, i + 1, j, connections) == 1 or query(i + 1, j + 1, i, j + 1, connections) == 1:
                            Set(i + 1, j + 1, i + 1, j, connections, 2, G, Gid)
                            Set(i + 1, j + 1, i, j + 1, connections, 2, G, Gid)
                    if (x[2] == 1 or x[3] == 1):
                        if query(i + 1, j + 1, i + 1, j, connections) == 2 or query(i + 1, j + 1, i, j + 1, connections) == 2:
                            Set(i + 1, j + 1, i + 1, j, connections, 1, G, Gid)
                            Set(i + 1, j + 1, i, j + 1, connections, 1, G, Gid)

                    x = getvx(i, j + 1, connections)
                    if x[2] == 2 and x[1] == 2:
                        if query(i + 1, j, i + 1, j + 1, connections) == 1 or query(i + 1, j, i, j, connections) == 1:
                            Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)
                            Set(i, j + 1, i, j, connections, 2, G, Gid)
                        if query(i + 1, j, i + 1, j + 1, connections) == 2 or query(i + 1, j, i, j, connections) == 2:
                            Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)
                            Set(i, j + 1, i, j, connections, 1, G, Gid)
                    if (x[2] == 1 and x[1] == 2) or (x[2] == 2 and x[1] == 1) or ((i, j + 1) in c and 1 in c[(i, j + 1)]):
                        if query(i + 1, j, i + 1, j + 1, connections) == 1 or query(i + 1, j, i, j, connections) == 1:
                            Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)
                            Set(i + 1, j, i, j, connections, 2, G, Gid)
                    if (x[2] == 1 or x[1] == 1):
                        if query(i + 1, j, i + 1, j + 1, connections) == 2 or query(i + 1, j, i, j, connections) == 2:
                            Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                            Set(i + 1, j, i, j, connections, 1, G, Gid)

                    x = getvx(i + 1, j, connections)
                    if x[0] == 2 and x[3] == 2:
                        if query(i, j + 1, i + 1, j + 1, connections) == 1 or query(i, j + 1, i, j, connections) == 1:
                            Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)
                            Set(i + 1, j, i, j, connections, 2, G, Gid)
                        if query(i, j + 1, i + 1, j + 1, connections) == 2 or query(i, j + 1, i, j, connections) == 2:
                            Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                            Set(i + 1, j, i, j, connections, 1, G, Gid)
                    if (x[0] == 1 and x[3] == 2) or (x[0] == 2 and x[3] == 1) or ((i + 1, j) in c and 3 in c[(i + 1, j)]):
                        if query(i, j + 1, i + 1, j + 1, connections) == 1 or query(i, j + 1, i, j, connections) == 1:
                            Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)
                            Set(i, j + 1, i, j, connections, 2, G, Gid)
                    if (x[0] == 1 or x[3] == 1):
                        if query(i, j + 1, i + 1, j + 1, connections) == 2 or query(i, j + 1, i, j, connections) == 2:
                            Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)
                            Set(i, j + 1, i, j, connections, 1, G, Gid)

                    x = getvx(i + 1, j + 1, connections)
                    if x[0] == 2 and x[1] == 2:
                        if query(i, j, i, j + 1, connections) == 1 or query(i, j, i + 1, j, connections) == 1:
                            Set(i + 1, j + 1, i, j + 1, connections, 2, G, Gid)
                            Set(i + 1, j + 1, i + 1, j, connections, 2, G, Gid)
                        if query(i, j, i, j + 1, connections) == 2 or query(i, j, i + 1, j, connections) == 2:
                            Set(i + 1, j + 1, i, j + 1, connections, 1, G, Gid)
                            Set(i + 1, j + 1, i + 1, j, connections, 1, G, Gid)
                    if (x[0] == 2 and x[1] == 1) or (x[0] == 1 and x[1] == 2) or ((i + 1, j + 1) in c and 2 in c[(i + 1, j + 1)]):
                        if query(i, j, i + 1, j, connections) == 1 or query(i, j, i, j + 1, connections) == 1:
                            Set(i, j, i + 1, j, connections, 2, G, Gid)
                            Set(i, j, i, j + 1, connections, 2, G, Gid)
                    if (x[0] == 1 or x[1] == 1):
                        if query(i, j, i + 1, j, connections) == 2 or query(i, j, i, j + 1, connections) == 2:
                            Set(i, j, i + 1, j, connections, 1, G, Gid)
                            Set(i, j, i, j + 1, connections, 1, G, Gid)

                    x1, x2 = getvx(i, j, connections), getvx(i + 1, j + 1, connections)
                    if (x1[2] == 1 or x1[3] == 1) and (x2[0] == 1 or x2[1] == 1):
                        Set(i, j, i - 1, j, connections, 2, G, Gid)
                        Set(i, j, i, j - 1, connections, 2, G, Gid)
                        Set(i + 1, j + 1, i + 1, j + 2, connections, 2, G, Gid)
                        Set(i + 1, j + 1, i + 2, j + 1, connections, 2, G, Gid)

                    x1, x2 = getvx(i + 1, j, connections), getvx(i, j + 1, connections)
                    if (x1[0] == 1 or x1[3] == 1) and (x2[1] == 1 or x2[2] == 1):
                        Set(i, j + 1, i - 1, j + 1, connections, 2, G, Gid)
                        Set(i, j + 1, i, j + 2, connections, 2, G, Gid)
                        Set(i + 1, j, i + 2, j, connections, 2, G, Gid)
                        Set(i + 1, j, i + 1, j - 1, connections, 2, G, Gid)

        for i in range(N + 1):
            for j in range(M + 1):
                x0, x1, x2 = getv(i, j, connections)
                if x1 == 2 or x2 > 2:
                    Set(i, j, i + 1, j, connections, 2, G, Gid)
                    Set(i, j, i, j + 1, connections, 2, G, Gid)
                    Set(i, j, i - 1, j, connections, 2, G, Gid)
                    Set(i, j, i, j - 1, connections, 2, G, Gid)
                if x1 == 1 and x2 == 2:
                    Set(i, j, i + 1, j, connections, 1, G, Gid)
                    Set(i, j, i, j + 1, connections, 1, G, Gid)
                    Set(i, j, i - 1, j, connections, 1, G, Gid)
                    Set(i, j, i, j - 1, connections, 1, G, Gid)

                gid = Gid[(i, j)]
                if (i, j + 1) in Gid and gid == Gid[(i, j + 1)] and quan(G) > 1:
                    Set(i, j, i, j + 1, connections, 2, G, Gid)
                if (i, j - 1) in Gid and gid == Gid[(i, j - 1)] and quan(G) > 1:
                    Set(i, j, i, j - 1, connections, 2, G, Gid)
                if (i - 1, j) in Gid and gid == Gid[(i - 1, j)] and quan(G) > 1:
                    Set(i, j, i - 1, j, connections, 2, G, Gid)
                if (i + 1, j) in Gid and gid == Gid[(i + 1, j)] and quan(G) > 1:
                    Set(i, j, i + 1, j, connections, 2, G, Gid)

        l = sum(len(connections[i]) for i in connections)
        if isvalid(matrix, connections, G, Gid) == 0:
            return 0

    if apply_search:
        return l

    suc = 1
    for i in range(N):
        for j in range(M):
            x0, x1, x2 = getm(i, j, connections)
            if x1 != matrix[i][j] and matrix[i][j] != 4:
                suc = 0
    if quan(G) != 1:
        suc = 0
    if suc:
        global solution
        solution = connections
        return 1

    couple_path = {}
    Gc = {}
    Gidc = {}
    gid = 0
    for i in range(N + 1):
        for j in range(M + 1):
            for (x, y) in [(i + 1, j), (i, j + 1)]:
                if i < 0 or i > N or j < 0 or j > M or x < 0 or x > N or y < 0 or y > M:
                    continue
                gid += 1
                Gc[gid] = [(i, j, x, y), (x, y, i, j)]
                Gidc[(i, j, x, y)] = gid
                Gidc[(x, y, i, j)] = gid

    for c in [find_couple(matrix, connections), find_couple_same(matrix, connections)]:
        for (i, j) in c:
            if 0 in c[(i, j)]:
                x1, y1, x2, y2 = i, j - 1, i - 1, j
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)
            if 1 in c[(i, j)]:
                x1, y1, x2, y2 = i, j + 1, i - 1, j
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)
            if 2 in c[(i, j)]:
                x1, y1, x2, y2 = i, j + 1, i + 1, j
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)
            if 3 in c[(i, j)]:
                x1, y1, x2, y2 = i, j - 1, i + 1, j
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)
            if 4 in c[(i, j)]:
                x1, y1, x2, y2 = i - 1, j, i + 1, j
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)
                x1, y1, x2, y2 = i, j - 1, i, j + 1
                if query(i, j, x1, y1, connections) == 0 and query(i, j, x2, y2, connections) == 0:
                    Setcouple(i, j, x1, y1, x2, y2, couple_path, 1, Gc, Gidc)

    global rr
    rr = []
    z = getzero(matrix, connections)
    for (i, j, x, y) in z:
        if (i, j) in connections and (x, y) in connections[(i, j)]:
            continue
        for v in [1, 2]:
            if search(matrix, copy.deepcopy(connections), copy.deepcopy(G), copy.deepcopy(Gid), deepth, i, j, x, y, v):
                Set(
                    i, j, x, y, connections, 3 - v, G, Gid,
                    debug=(
                        f"contradiction on assume {((i, j), (x, y))}={'line' if v == 1 else 'empty'}"
                        if _log_level == "brief"
                        else f"assuming edge {((i, j), (x, y))} as {'line' if v == 1 else 'empty'} causes contradiction, so force {'line' if (3 - v) == 1 else 'empty'}."
                    ),
                )
                solve_core(matrix, connections, G, Gid, deepth + 1, apply_search=True)
                break
    if len(rr) == 0:
        return -1
    return solve_core(matrix, connections, G, Gid, deepth + 1)


def search(matrix, connections, G, Gid, deepth, i, j, x, y, v):
    global rr, _log_suspend
    prev_suspend = _log_suspend
    _log_suspend += 1
    try:
        r1 = solve_core(matrix, copy.deepcopy(connections), copy.deepcopy(G), copy.deepcopy(Gid), deepth + 1, apply_search=True, extra=(i, j, x, y, v))
    finally:
        _log_suspend = prev_suspend
    if r1 == 0:
        rr.append((i, j, x, y, 3 - v))
        return 1
    return 0


def apply_init_rules(matrix, connections, G, Gid):
    for i in range(N):
        for j in range(M):
            if matrix[i][j] == 0:
                Set(i, j, i + 1, j, connections, 2, G, Gid)
                Set(i + 1, j, i + 1, j + 1, connections, 2, G, Gid)
                Set(i, j, i, j + 1, connections, 2, G, Gid)
                Set(i, j + 1, i + 1, j + 1, connections, 2, G, Gid)

    for i in range(N):
        for j in range(M):
            if matrix[i][j] == 3:
                if j < M - 1 and matrix[i][j + 1] == 3:
                    Set(i, j, i + 1, j, connections, 1, G, Gid)
                    Set(i, j + 1, i + 1, j + 1, connections, 1, G, Gid)
                    Set(i, j + 2, i + 1, j + 2, connections, 1, G, Gid)
                    Set(i, j + 1, i - 1, j + 1, connections, 2, G, Gid)
                    Set(i + 1, j + 1, i + 2, j + 1, connections, 2, G, Gid)

                if i < N - 1 and matrix[i + 1][j] == 3:
                    Set(i, j, i, j + 1, connections, 1, G, Gid)
                    Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                    Set(i + 2, j, i + 2, j + 1, connections, 1, G, Gid)
                    Set(i + 1, j, i + 1, j - 1, connections, 2, G, Gid)
                    Set(i + 1, j + 1, i + 1, j + 2, connections, 2, G, Gid)

                a = i + 1
                b = j + 1
                while a < N and b < M and matrix[a][b] == 2:
                    a += 1
                    b += 1
                if a < N and b < M and matrix[a][b] == 3:
                    Set(i, j, i, j + 1, connections, 1, G, Gid)
                    Set(i, j, i + 1, j, connections, 1, G, Gid)
                    Set(a + 1, b + 1, a + 1, b, connections, 1, G, Gid)
                    Set(a + 1, b + 1, a, b + 1, connections, 1, G, Gid)

                a = i - 1
                b = j + 1
                while a >= 0 and b < M and matrix[a][b] == 2:
                    a -= 1
                    b += 1
                if a >= 0 and b < M and matrix[a][b] == 3:
                    Set(i, j, i + 1, j, connections, 1, G, Gid)
                    Set(i + 1, j, i + 1, j + 1, connections, 1, G, Gid)
                    Set(a, b + 1, a, b, connections, 1, G, Gid)
                    Set(a, b + 1, a + 1, b + 1, connections, 1, G, Gid)


def matrix_from_observation(observation):
    data = observation
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    rows = len(data)
    cols = len(data[0])
    matrix = [[4 for _ in range(cols)] for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            if data[i][j] is not None:
                matrix[i][j] = int(data[i][j])
    return matrix


def extract_path(sol_connections):
    lines = {}
    for a, nxts in sol_connections.items():
        for b, v in nxts.items():
            if v == 1:
                lines.setdefault(a, []).append(b)
    start = None
    for k, v in lines.items():
        if len(v) > 0:
            start = k
            break
    if start is None:
        return []
    path = [start]
    prev = None
    cur = start
    cap = (N + 1) * (M + 1) * 4
    step = 0
    while step < cap:
        step += 1
        nxt = None
        for nb in lines.get(cur, []):
            if nb != prev:
                nxt = nb
                break
        if nxt is None:
            break
        path.append(nxt)
        if nxt == start:
            break
        prev, cur = cur, nxt
    return path


def solve_one(observation):
    global N, M, lastfalse, rr, solution
    matrix = matrix_from_observation(observation)
    N = len(matrix)
    M = len(matrix[0]) if matrix else 0
    lastfalse = {}
    rr = []
    solution = {}

    connections = {}
    G = {}
    Gid = {}
    gid = 0
    for i in range(N + 1):
        for j in range(M + 1):
            gid += 1
            G[gid] = [(i, j)]
            Gid[(i, j)] = gid

    apply_init_rules(matrix, connections, G, Gid)
    ret = solve_core(matrix, connections, G, Gid, 1)
    if ret == 1:
        return extract_path(solution)
    return []


def _normalize_observation(observation):
    if isinstance(observation, dict) and observation:
        # coordinate-dict observation: {(0.5,1.5):2} or {"0.5,1.5":2} / {"(0.5,1.5)":2}
        def _parse_coord_key(k):
            if isinstance(k, tuple) and len(k) == 2:
                return float(k[0]), float(k[1])
            if isinstance(k, str):
                s = k.strip()
                if s.startswith("(") and s.endswith(")"):
                    s = s[1:-1].strip()
                if "," in s:
                    a, b = s.split(",", 1)
                    return float(a.strip()), float(b.strip())
            raise ValueError("bad coordinate key")

        coord_mode = True
        clues: Dict[Tuple[int, int], int] = {}
        mr = -1
        mc = -1
        try:
            for k, v in observation.items():
                r, c = _parse_coord_key(k)
                rr2 = int(round(float(r) - 0.5))
                cc2 = int(round(float(c) - 0.5))
                clues[(rr2, cc2)] = int(v)
                mr = max(mr, rr2)
                mc = max(mc, cc2)
        except Exception:
            coord_mode = False

        if coord_mode and clues:
            # Observation-only clue dict does not encode trailing empty rows/cols.
            # Slitherlink data in this project is square, so expand to max side.
            side = max(mr, mc) + 1
            rows = side
            cols = side
            grid: List[List[int | None]] = [[None for _ in range(cols)] for _ in range(rows)]
            for (r, c), v in clues.items():
                grid[r][c] = v
            return {"data": grid}

    obs = observation
    if isinstance(obs, dict):
        if "data" in obs:
            return {"data": obs["data"]}
        if "original_data" in obs and isinstance(obs["original_data"], dict) and "data" in obs["original_data"]:
            return {"data": obs["original_data"]["data"]}

    if isinstance(obs, list) and obs and isinstance(obs[0], list):
        return {"data": obs}

    raise ValueError("unsupported slitherlink observation")



def solve(
    observation,
    verbose: bool = False,
    max_logs: int = 8000,
    log_level: str = "brief",
    check_unique: bool = True,
):
    normalized = _normalize_observation(observation)
    answer = solve_one(normalized)
    if not answer:
        return "No Solution"
    return answer
