# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/methods/02_dice.ipynb.

# %% ../../nbs/methods/02_dice.ipynb 3
from __future__ import annotations
from ..import_essentials import *
from .base import CFModule
from ..base import BaseConfig
from ..utils import auto_reshaping, grad_update, validate_configs

# %% auto 0
__all__ = ['dpp_style_vmap', 'DiverseCFConfig', 'DiverseCF']

# %% ../../nbs/methods/02_dice.ipynb 6
@jit
def dpp_style_vmap(cfs: Array):
    def dpp_fn(cf_1, cf_2):
        return 1 / (1 + jnp.linalg.norm(cf_1 - cf_2, ord=1))
    
    det_entries = vmap(vmap(dpp_fn, in_axes=(None, 0)), in_axes=(0, None))(cfs, cfs)
    det_entries += jnp.eye(cfs.shape[0]) * 1e-8
    assert det_entries.shape == (cfs.shape[0], cfs.shape[0])
    return jnp.linalg.det(det_entries)

# %% ../../nbs/methods/02_dice.ipynb 13
def _diverse_cf(
    x: jnp.DeviceArray,  # `x` shape: (k,), where `k` is the number of features
    y_target: Array, # `y_target` shape: (1,)
    pred_fn: Callable[[Array], Array],  # y = pred_fn(x)
    n_cfs: int,
    n_steps: int,
    lr: float,  # learning rate for each `cf` optimization step
    lambdas: Tuple[float, float, float, float], # (lambda_1, lambda_2, lambda_3, lambda_4)
    key: jrand.PRNGKey,
    validity_fn: Callable,
    cost_fn: Callable,
    apply_constraints_fn: Callable,
    compute_reg_loss_fn: Callable,
) -> Array:  # return `cf` shape: (k,)
    """Diverse Counterfactuals (Dice) algorithm."""

    def loss_fn(
        cfs: Array, # shape: (n_cfs, k)
        x: Array, # shape: (1, k)
        pred_fn: Callable[[Array], Array], # y = pred_fn(x)
        y_target: Array,
    ):
        cf_y_pred = pred_fn(cfs)
        loss_1 = validity_fn(y_target, cf_y_pred).mean()
        loss_2 = cost_fn(x, cfs).mean()
        loss_3 = - dpp_style_vmap(cfs).mean()
        loss_4 = compute_reg_loss_fn(x, cfs)
        return (
            lambda_1 * loss_1 + 
            lambda_2 * loss_2 + 
            lambda_3 * loss_3 + 
            lambda_4 * loss_4
        )
    
    @loop_tqdm(n_steps)
    def gen_cf_step(i, states: Tuple[Array, optax.OptState]):
        cf, opt_state = states
        grads = jax.grad(loss_fn)(cf, x, pred_fn, y_target)
        cf_updates, opt_state = grad_update(grads, cf, opt_state, opt)
        return cf, opt_state
    
    lambda_1, lambda_2, lambda_3, lambda_4 = lambdas
    key, subkey = jrand.split(key)
    cfs = jrand.normal(key, (n_cfs, x.shape[-1]))
    opt = optax.adam(lr)
    opt_state = opt.init(cfs)
    
    cfs, opt_state = lax.fori_loop(0, n_steps, gen_cf_step, (cfs, opt_state))
    # TODO: support return multiple cfs
    # cfs = apply_constraints_fn(x, cfs[:1, :], hard=True)
    cfs = apply_constraints_fn(x, cfs, hard=True)
    return cfs


# %% ../../nbs/methods/02_dice.ipynb 15
class DiverseCFConfig(BaseConfig):
    n_cfs: int = 5
    n_steps: int = 1000
    lr: float = 0.001
    lambda_1: float = 1.0
    lambda_2: float = 0.1
    lambda_3: float = 1.0
    lambda_4: float = 0.1
    validity_fn: str = 'KLDivergence'
    cost_fn: str = 'MeanSquaredError'
    seed: int = 42


# %% ../../nbs/methods/02_dice.ipynb 16
class DiverseCF(CFModule):

    def __init__(self, config: dict | DiverseCF = None, *, name: str = None):
        if config is None:
             config = DiverseCFConfig()
        config = validate_configs(config, DiverseCFConfig)
        name = "DiverseCF" if name is None else name
        super().__init__(config, name=name)

    @auto_reshaping('x', reshape_output=False)
    def generate_cf(
        self,
        x: Array,  # `x` shape: (k,), where `k` is the number of features
        pred_fn: Callable[[Array], Array],
        y_target: Array = None,
        rng_key: jnp.ndarray = None,
        **kwargs,
    ) -> jnp.DeviceArray:
        # TODO: Currently assumes binary classification.
        if y_target is None:
            y_target = 1 - pred_fn(x)
        else:
            y_target = jnp.array(y_target, copy=True)
        if rng_key is None:
            rng_key = jax.random.PRNGKey(self.config.seed)
        
        return _diverse_cf(
            x=x,  # `x` shape: (k,), where `k` is the number of features
            y_target=y_target,  # `y_target` shape: (1,)
            pred_fn=pred_fn,  # y = pred_fn(x)
            n_cfs=self.config.n_cfs,
            n_steps=self.config.n_steps,
            lr=self.config.lr,  # learning rate for each `cf` optimization step
            lambdas=(
                self.config.lambda_1, self.config.lambda_2, 
                self.config.lambda_3, self.config.lambda_4
            ),
            key=rng_key,
            validity_fn=keras.losses.get({'class_name': self.config.validity_fn, 'config': {'reduction': None}}),
            cost_fn=keras.losses.get({'class_name': self.config.cost_fn, 'config': {'reduction': None}}),
            apply_constraints_fn=self.apply_constraints_fn,
            compute_reg_loss_fn=self.compute_reg_loss_fn,
        )
