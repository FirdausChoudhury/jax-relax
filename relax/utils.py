# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_utils.ipynb.

# %% ../nbs/00_utils.ipynb 3
from __future__ import annotations
from .import_essentials import *
import nbdev
from fastcore.basics import AttrDict
from nbdev.showdoc import BasicMarkdownRenderer
from inspect import isclass
from fastcore.test import *
from jax.core import InconclusiveDimensionOperation

# %% auto 0
__all__ = ['validate_configs', 'save_pytree', 'load_pytree', 'auto_reshaping', 'grad_update', 'load_json', 'get_config',
           'set_config']

# %% ../nbs/00_utils.ipynb 5
def validate_configs(
    configs: dict | BaseParser,  # A configuration of the model/dataset.
    config_cls: BaseParser,  # The desired configuration class.
) -> BaseParser:
    """return a valid configuration object."""

    assert isclass(config_cls), f"`config_cls` should be a class."
    assert issubclass(config_cls, BaseParser), \
        f"{config_cls} should be a subclass of `BaseParser`."
    
    if isinstance(configs, dict):
        configs = config_cls(**configs)
    if not isinstance(configs, config_cls):
        raise TypeError(
            f"configs should be either a `dict` or an instance of {config_cls.__name__}.")
    return configs

# %% ../nbs/00_utils.ipynb 15
def _is_array(x):
    return isinstance(x, np.ndarray) or isinstance(x, jnp.ndarray) or isinstance(x, list)

def save_pytree(pytree, saved_dir):
    """Save a pytree to a directory."""
    with open(os.path.join(saved_dir, "data.npy"), "wb") as f:
        for x in jax.tree_util.tree_leaves(pytree):
            np.save(f, x)

    tree_struct = jax.tree_util.tree_map(lambda t: _is_array(t), pytree)
    with open(os.path.join(saved_dir, "treedef.json"), "w") as f:
        json.dump(tree_struct, f)

# %% ../nbs/00_utils.ipynb 20
def load_pytree(saved_dir):
    """Load a pytree from a saved directory."""
    with open(os.path.join(saved_dir, "treedef.json"), "r") as f:
        tree_struct = json.load(f)

    leaves, treedef = jax.tree_util.tree_flatten(tree_struct)
    with open(os.path.join(saved_dir, "data.npy"), "rb") as f:
        flat_state = [
            np.load(f, allow_pickle=True) if is_arr else np.load(f, allow_pickle=True).item()
            for is_arr in leaves
        ]
    return jax.tree_util.tree_unflatten(treedef, flat_state)

# %% ../nbs/00_utils.ipynb 25
def _reshape_x(x: Array):
    x_size = x.shape
    if len(x_size) > 1 and x_size[0] != 1:
        raise ValueError(
            f"""Invalid Input Shape: Require `x.shape` = (1, k) or (k, ),
but got `x.shape` = {x.shape}. This method expects a single input instance."""
        )
    if len(x_size) == 1:
        x = x.reshape(1, -1)
    return x, x_size

# %% ../nbs/00_utils.ipynb 26
def auto_reshaping(
    reshape_argname: str, # The name of the argument to be reshaped.
    reshape_output: bool = True, # Whether to reshape the output. Useful to set `False` when returning multiple cfs.
):
    """
    Decorator to automatically reshape function's input into (1, k), 
    and out to input's shape.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            kwargs = inspect.getcallargs(func, *args, **kwargs)
            if reshape_argname in kwargs:
                reshaped_x, x_shape = _reshape_x(kwargs[reshape_argname])
                kwargs[reshape_argname] = reshaped_x
            else:
                raise ValueError(
                    f"Invalid argument name: `{reshape_argname}` is not a valid argument name.")
            # Call the function.
            cf = func(**kwargs)
            if not isinstance(cf, Array): 
                raise ValueError(
                    f"Invalid return type: must be a `jax.Array`, but got `{type(cf).__name__}`.")
            if reshape_output:
                try: 
                    cf = cf.reshape(x_shape)
                except (InconclusiveDimensionOperation, TypeError) as e:
                    raise ValueError(
                        f"Invalid return shape: Require `cf.shape` = {cf.shape} "
                        f"is not compatible with `x.shape` = {x_shape}.")
            return cf

        return wrapper
    return decorator

# %% ../nbs/00_utils.ipynb 31
def grad_update(
    grads, # A pytree of gradients.
    params, # A pytree of parameters.
    opt_state: optax.OptState,
    opt: optax.GradientTransformation,
): # Return (upt_params, upt_opt_state)
    updates, opt_state = opt.update(grads, opt_state, params)
    upt_params = optax.apply_updates(params, updates)
    return upt_params, opt_state

# %% ../nbs/00_utils.ipynb 33
def load_json(f_name: str) -> Dict[str, Any]:  # file name
    with open(f_name) as f:
        return json.load(f)


# %% ../nbs/00_utils.ipynb 35
@dataclass
class Config:
    rng_reserve_size: int
    global_seed: int

    @classmethod
    def default(cls) -> Config:
        return cls(rng_reserve_size=1, global_seed=42)

main_config = Config.default()

# %% ../nbs/00_utils.ipynb 36
def get_config() -> Config: 
    return main_config

# %% ../nbs/00_utils.ipynb 37
def set_config(
        *,
        rng_reserve_size: int = None, # The number of random number generators to reserve.
        global_seed: int = None, # The global seed for random number generators.
        **kwargs
) -> None:
    """Sets the global configurations."""

    def set_val(
            arg_name: str, # The name of the argument.
            arg_value: int, # The value of the argument.
            arg_min: int # The minimum value of the argument.
    ) -> None:
        """Checks the validity of the argument and sets the value."""
        
        if arg_value is None or not hasattr(main_config, arg_name):
            return
        
        if not isinstance(arg_value, int):
            raise TypeError(f"`{arg_name}` must be an integer, but got {type(arg_value).__name__}.")
        if arg_value < arg_min:
            raise ValueError(f"`{arg_name}` must be non-negative, but got {arg_value}.")
        setattr(main_config, arg_name, arg_value)

    set_val('rng_reserve_size', rng_reserve_size, 1)
    set_val('global_seed', global_seed, 0)
