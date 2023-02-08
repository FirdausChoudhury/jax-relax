# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_training_module.ipynb.

# %% ../nbs/03_training_module.ipynb 3
from __future__ import annotations
from .import_essentials import *
from .data import TabularDataModule
from .logger import TensorboardLogger
from .utils import validate_configs, sigmoid, accuracy, init_net_opt, grad_update, make_hk_module, show_doc as show_parser_doc
from fastcore.basics import patch
from functools import partial
from abc import ABC, abstractmethod
from copy import deepcopy

# %% auto 0
__all__ = ['BaseNetwork', 'DenseBlock', 'MLP', 'PredictiveModel', 'BaseTrainingModule', 'PredictiveTrainingModuleConfigs',
           'PredictiveTrainingModule']

# %% ../nbs/03_training_module.ipynb 5
class BaseNetwork(ABC):
    """BaseNetwork needs a `is_training` argument"""

    def __call__(self, *, is_training: bool):
        pass


# %% ../nbs/03_training_module.ipynb 6
class DenseBlock(hk.Module):
    """A `DenseBlock` consists of a dense layer, followed by Leaky Relu and a dropout layer."""
    
    def __init__(
        self,
        output_size: int,  # Output dimensionality.
        dropout_rate: float = 0.3,  # Dropout rate.
        name: str | None = None,  # Name of the Module
    ):
        super().__init__(name=name)
        self.output_size = output_size
        self.dropout_rate = dropout_rate

    def __call__(self, x: jnp.ndarray, is_training: bool = True) -> jnp.ndarray:
        dropout_rate = self.dropout_rate if is_training else 0.0
        # he_uniform
        w_init = hk.initializers.VarianceScaling(2.0, "fan_in", "uniform")
        x = hk.Linear(self.output_size, w_init=w_init)(x)
        x = jax.nn.leaky_relu(x)
        x = hk.dropout(hk.next_rng_key(), dropout_rate, x)
        return x


# %% ../nbs/03_training_module.ipynb 7
class MLP(hk.Module):
    """A `MLP` consists of a list of `DenseBlock` layers."""
    
    def __init__(
        self,
        sizes: Iterable[int],  # Sequence of layer sizes.
        dropout_rate: float = 0.3,  # Dropout rate.
        name: str | None = None,  # Name of the Module
    ):
        super().__init__(name=name)
        self.sizes = sizes
        self.dropout_rate = dropout_rate

    def __call__(self, x: jnp.ndarray, is_training: bool = True) -> jnp.ndarray:
        for size in self.sizes:
            x = DenseBlock(size, self.dropout_rate)(x, is_training)
        return x


# %% ../nbs/03_training_module.ipynb 9
class PredictiveModelConfigs(BaseParser):
    """Configurator of `PredictiveModel`."""

    sizes: List[int]  # Sequence of layer sizes.
    dropout_rate: float = 0.3  # Dropout rate.


# %% ../nbs/03_training_module.ipynb 10
class PredictiveModel(hk.Module):
    """A basic predictive model for binary classification."""
    
    def __init__(
        self,
        sizes: List[int], # Sequence of layer sizes.
        dropout_rate: float = 0.3,  # Dropout rate.
        name: Optional[str] = None,  # Name of the module.
    ):
        """A basic predictive model for binary classification."""
        super().__init__(name=name)
        self.configs = PredictiveModelConfigs(
            sizes=sizes, dropout_rate=dropout_rate
        )

    def __call__(self, x: jnp.ndarray, is_training: bool = True) -> jnp.ndarray:
        x = MLP(sizes=self.configs.sizes, dropout_rate=self.configs.dropout_rate)(
            x, is_training
        )
        x = hk.Linear(1)(x)
        x = jax.nn.sigmoid(x)
        # x = sigmoid(x)
        return x


# %% ../nbs/03_training_module.ipynb 25
class BaseTrainingModule(ABC):
    hparams: Dict[str, Any]
    logger: TensorboardLogger | None

    def save_hyperparameters(self, configs: Dict[str, Any]) -> Dict[str, Any]:
        self.hparams = deepcopy(configs)
        return self.hparams

    def init_logger(self, logger: TensorboardLogger):
        self.logger = logger

    def log(self, name: str, value: Any):
        self.log_dict({name: value})

    def log_dict(self, dictionary: Dict[str, Any]):
        if self.logger:
            # self.logger.log({k: np.asarray(v) for k, v in dictionary.items()})
            self.logger.log_dict(dictionary)
        else:
            raise ValueError("Logger has not been initliazed.")

    @abstractmethod
    def init_net_opt(
        self, data_module: TabularDataModule, key: random.PRNGKey
    ) -> Tuple[hk.Params, optax.OptState]:
        pass

    @abstractmethod
    def training_step(
        self,
        params: hk.Params,
        opt_state: optax.OptState,
        rng_key: random.PRNGKey,
        batch: Tuple[jnp.array, jnp.array],
    ) -> Tuple[hk.Params, optax.OptState]:
        pass

    @abstractmethod
    def validation_step(
        self,
        params: hk.Params,
        rng_key: random.PRNGKey,
        batch: Tuple[jnp.array, jnp.array],
    ) -> Dict[str, Any]:
        pass


# %% ../nbs/03_training_module.ipynb 27
class PredictiveTrainingModuleConfigs(BaseParser):
    """Configurator of `PredictiveTrainingModule`."""
    
    lr: float = Field(description='Learning rate.')
    sizes: List[int] = Field(description='Sequence of layer sizes.')
    dropout_rate: float = Field(0.3, description='Dropout rate') 

# %% ../nbs/03_training_module.ipynb 28
class PredictiveTrainingModule(BaseTrainingModule):
    """A training module for predictive models."""
    
    def __init__(self, m_configs: Dict | PredictiveTrainingModuleConfigs):
        self.save_hyperparameters(m_configs)
        self.configs = validate_configs(m_configs, PredictiveTrainingModuleConfigs)
        self.net = make_hk_module(
            PredictiveModel, 
            sizes=self.configs.sizes, 
            dropout_rate=self.configs.dropout_rate
        )
        self.opt = optax.adam(learning_rate=self.configs.lr)

    @partial(jax.jit, static_argnames=["self", "is_training"])
    def forward(self, params, rng_key, x, is_training: bool = True):
        return self.net.apply(params, rng_key, x, is_training=is_training)

    def init_net_opt(self, data_module, key):
        X, _ = data_module.train_dataset[:100]
        params, opt_state = init_net_opt(
            self.net, self.opt, X=X, key=key
        )
        return params, opt_state

    def loss_fn(self, params, rng_key, batch, is_training: bool = True):
        x, y = batch
        y_pred = self.net.apply(params, rng_key, x, is_training=is_training)
        return jnp.mean(vmap(optax.l2_loss)(y_pred, y))

    # def _training_step(self, params, opt_state, rng_key, batch):
    #     grads = jax.grad(self.loss_fn)(params, rng_key, batch)
    #     upt_params, opt_state = grad_update(grads, params, opt_state, self.opt)
    #     return upt_params, opt_state

    @partial(jax.jit, static_argnames=["self"])
    def _training_step(self, params, opt_state, rng_key, batch):
        grads = jax.grad(self.loss_fn)(params, rng_key, batch)
        upt_params, opt_state = grad_update(grads, params, opt_state, self.opt)
        return upt_params, opt_state

    def training_step(self, params, opt_state, rng_key, batch):
        params, opt_state = self._training_step(params, opt_state, rng_key, batch)

        loss = self.loss_fn(params, rng_key, batch)
        self.log_dict({"train/train_loss_1": loss.item()})
        return params, opt_state

    def validation_step(self, params, rng_key, batch):
        x, y = batch
        y_pred = self.net.apply(params, rng_key, x, is_training=False)
        loss = self.loss_fn(params, rng_key, batch, is_training=False)
        logs = {"val/val_loss": loss.item(), "val/val_accuracy": accuracy(y, y_pred)}
        self.log_dict(logs)

