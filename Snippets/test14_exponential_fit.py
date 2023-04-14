"""https://randorithms.com/2020/03/08/exponential-sum-fits.html"""

import numpy as np
import matplotlib.pyplot as plt


def E(n, a, theta):
    # Exponential sum function for n and the model (a,theta)
    y = np.zeros_like(n, dtype=np.complex128)  # np.float64
    for ai, theta_i in zip(a, theta):
        y += ai * theta_i ** n
    return np.abs(y)  # return y


def R0(X, n, a, theta):
    # Empirical risk associated with the current model (a,theta)
    return np.sum((X - E(n, a, theta)) ** 2)


def P(grid_thetas, X, n, a, theta):
    # Residual polynomial (from the paper)
    y = np.zeros_like(grid_thetas)
    for ni in n:
        y += 2 * (E(ni, a, theta) - X[ni]) * grid_thetas ** ni
    return y


def linear_stage(A, X):
    # Simple linear regression to find the amplitudes
    sol = np.linalg.lstsq(A, X)
    a_new = sol[0]
    return a_new


def drop_negatives(a_old, a_new):
    # Begin minor iteration to remove negative terms from the fit
    if (np.min(a_new) < 0):
        min_idx = -1  # index k, in the paper
        min_beta = float('inf')  # beta_k, in the paper
        for idx, (aoi, ani) in enumerate(zip(a_old, a_new)):
            # aoi = a_old idx, ani = a_new idx
            if ani < 0:
                # guaranteed to be true for one
                # of the amplitudes, see outer "if" statement
                beta = aoi / (aoi - ani)
                if beta < min_beta:
                    min_beta = beta
                    min_idx = idx
        # Now update a_old
        a_old = (1 - min_beta) * a_old + min_beta * a_new
        a_old[min_idx] = 0
        return (min_idx, a_old)
    else:
        return (None, None)


def coalesceTerms(a, theta, M):
    # Coalesces terms until M terms remain
    N = len(theta)
    if N <= M:  # quit if we have M (or fewer) terms
        return (a, theta)
    while N > M:
        # find closest pair
        mind = float('inf')
        minidx = (0, 0)
        for i in range(N):
            for j in range(N):
                d = np.abs(theta[i] - theta[j])
                if d < mind:
                    mind = d
                    minidx = (i, j)

        a_new = a[i] + a[j]
        t_new = 0.5 * (theta[i] + theta[j])
        a[i] = a_new
        theta[i] = t_new
        a = np.delete(a, j)
        theta = np.delete(theta, j)
        N = len(theta)
    return (a, theta)


def fitEDSF(y, n, M=None, epsilon_1=10e-20, epsilon_2=10e-20, min_exponent_cutoff=0.0, number_of_thetas_to_try=100000):
    # fit exponential decay sum function
    # y: the exponential sum fit values to be fitted against
    # n: equally-spaced and contiguous points of n
    #    for instance, n = np.array([1,2,3,4,5,6,7,8])
    # M: model order. If None, then the model runs to convergence.
    #    if given, then the model returns exactly M components
    # epsilon_1: convergence criteria 1 from paper, default works well
    # epsilon_2: convergence criteria 2 from paper, default works well

    # Convergence flags
    converged = False
    R0_old = None
    R0_new = None

    # Parameters
    a_old = np.array([])  # set of amplitude values from previous iter
    a = np.array([])  # set of amplitude values
    theta = []  # theta is a list, need to append often

    iters = 0
    while not converged:
        a_old = a  # update previous iteration values

        # 1. Nonlinear part - find a good theta (rate)
        # add theta to minimize the residual polynomial P
        grid_thetas = np.linspace(min_exponent_cutoff, 1, number_of_thetas_to_try)
        P_theta = P(grid_thetas, y, n, a, theta)
        idx = np.argmin(P_theta)
        theta_new = grid_thetas[idx]
        theta.append(theta_new)

        # 2. Now set up linear regression problem to find the
        # amplitudes from the system y = A*a
        A = np.zeros((len(n), len(theta)), dtype=np.float64)
        for i, theta_i in enumerate(theta):
            A[:, i] = theta_i ** n

        a_new = linear_stage(A, y)
        a_old = np.append(a_old, 0)

        # 3. Eliminate terms with negative a_i
        drop_index, a_old = drop_negatives(a_old, a_new)
        while drop_index is not None:
            # delete the negative term
            a_old = np.delete(a_old, drop_index)
            A = np.delete(A, drop_index, axis=1)
            del theta[drop_index]
            a_new = linear_stage(A, y)  # find new a_i
            # ensure new a_i > 0
            drop_index, a_old = drop_negatives(a_old, a_new)

        # 4. Have we converged?
        a = a_new
        R0_new = R0(y, n, a, theta)

        if R0_old is not None:
            E1 = (R0_old - R0_new) / (R0_old)
            if E1 < epsilon_1:
                converged = True

        E2 = P_theta[idx]
        if E2 >= epsilon_2:
            converged = True

        # If we don't have M components
        # keep iterating
        if M is not None:
            if len(theta) < M:
                converged = False
        iters += 1
        print(iters)
        if iters > 200:
            converged = True

        R0_old = R0_new

    # Found a good fit, return coefficients
    theta = np.array(theta)
    a = np.array(a)
    if M is not None:
        a, theta = coalesceTerms(a, theta, M)

    final_err = R0(y, n, a, theta)
    return (a, theta, final_err)


def plot_result(a, theta, N, label):
    n = np.arange(0, N, 0.1)

    ans = {}
    for i in n:
        ans[i] = 0

    for mult, power in zip(a, theta):
        for i in n:
            ans[i] += mult * (power ** i)

    plt.plot(ans.keys(), ans.values(), 'x-', label=label)
    plt.legend()
    plt.show()


def plot_cum_exponents(a, theta, normalize=False):
    l = list(zip(a, theta))
    l.sort(key=lambda x: x[1])

    bins = []
    data = []

    for a_i, theta_i in l:
        bins.append(float(theta_i))
        data.append(float(a_i))

    plt.scatter(bins, data, marker='x', color='red', vmax=1, vmin=0)
    plt.show()

    sum_of_coefficients = 0
    for item in l:
        sum_of_coefficients += item[0]

    ll = [(1, 2)] * len(l)
    cumulative = 0
    for i, item in enumerate(l):
        if normalize:
            cumulative += item[0] / sum_of_coefficients
        else:
            cumulative += item[0]
        ll[i] = (item[1], cumulative)

    ll.insert(0, (0, 0))
    # ll.append((1, 1))

    plt.stairs([item[1] for item in ll][:-1], [item[0] for item in ll], baseline=0, fill=True)  # method 1
    plt.step([item[0] for item in ll], [item[1] for item in ll], where='post', color='red')  # method 2

    plt.xlabel('Real exponents')
    plt.ylabel('Cumulative multipliers')

    plt.gcf().set_size_inches(10, 6)
    plt.xlim([0.95, 1.0])
    plt.ylim([0.0, 0.025])

    plt.savefig('../Exponential decay data/' + file_name + '_result.png', )
    plt.show()

    print(ll)


if __name__ == "__main__":
    # rates = (0.1, 0.5, 0.8)
    # N = 10  # number of points
    ##
    # n = np.arange(0, N, 1)
    # y = np.zeros_like(n, dtype=np.float64)
    # for r in rates[0:]:
    #    y += r ** n
    # y += 1  # DC
    #
    # plot_cum_exponents([1., 1., 1., 1.], [0.1, 0.5, 0.8, 1])

    # print(y)

    import numpy as np

    file_name = 'tek0055'

    arr = np.loadtxt("../Exponential decay data/" + file_name + '.csv', delimiter=",", skiprows=22)

    # select portion of data,
    # since different portions of plot have slightly different coefficients

    # arr = arr[int(len(arr) * 0.5):int(len(arr) * 1.0)]

    N = len(arr)
    # n = arr[:, 0]
    n = np.arange(0, N, 1)
    y = arr[:, 1]
    y += 1  # DC bugfix in case data has slightly negative offset

    a, theta, err = fitEDSF(y, n, 20, min_exponent_cutoff=0.98, number_of_thetas_to_try=2000)
    print(a, theta, err)

    plt.plot(n, y, 'x-', label='initial data')
    plot_result(a, theta, N, label='fit 1')
    plot_cum_exponents(a, theta, normalize=False)

    print()
