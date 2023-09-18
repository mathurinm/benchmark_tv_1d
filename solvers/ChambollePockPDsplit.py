from benchopt import BaseSolver
from benchopt.stopping_criterion import SufficientDescentCriterion
from benchopt import safe_import_context

with safe_import_context() as import_ctx:
    import numpy as np
    from benchmark_utils.shared import get_l2norm


class Solver(BaseSolver):
    """Chambolle-Pock (or PDHG) on higher dual (PD-Split) for analysis."""

    name = "Chambolle-Pock PD-split analysis"

    stopping_criterion = SufficientDescentCriterion(
        patience=3, strategy="callback"
    )

    # any parameter defined here is accessible as a class attribute
    parameters = {'ratio': [1.0],
                  'theta': [1.0]}

    def set_objective(self, A, reg, y, c, delta, data_fit):
        self.reg = reg
        self.A, self.y = A, y
        self.c = c
        self.delta = delta
        self.data_fit = data_fit

    def run(self, callback):
        n, p = self.A.shape
        # Block preconditioning (2x2)
        LD = 2.0  # Lipschitz constant associated to D (only for 1d!!)
        LA = get_l2norm(self.A)
        tau = self.ratio / (LA + LD)
        sigma_v = 1.0 / (self.ratio * LD)
        sigma_w = 1.0 / (self.ratio * LA)
        # Init variables
        v = np.zeros(p - 1)  # we consider non-cyclic finite difference
        w = np.zeros(n)
        self.u = np.zeros(p)
        u_bar = self.u.copy()

        while callback():
            u_old = self.u
            v = np.clip(v + sigma_v * np.diff(u_bar),
                        -self.reg, self.reg)
            w_tmp = w + sigma_w * self.A @ u_bar
            if self.data_fit == "huber":
                # Use Moreau identity + translation rule
                prox_out = self._prox_huber(
                    w_tmp / sigma_w - self.y, 1.0 / sigma_w
                )
                w = w_tmp - sigma_w * (prox_out + self.y)
            else:
                w = (w_tmp - sigma_w * self.y) / (1.0 + sigma_w)
            # grad.T = -div, hence + sign
            self.u += tau * (np.diff(v, prepend=0, append=0) - self.A.T @ w)
            u_bar = self.u + self.theta * (self.u - u_old)

    def get_result(self):
        return dict(u=self.u)

    def _prox_huber(self, u, mu):
        return np.where(
            np.abs(u) <= self.delta * (mu + 1.0),
            u / (mu + 1.0),
            u - self.delta * mu * np.sign(u),
        )
