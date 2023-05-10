# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/methods/06_cchvae.ipynb.

# %% ../../nbs/methods/06_cchvae.ipynb 3
from __future__ import annotations
from ..import_essentials import *
from .base import BaseCFModule, BaseParametricCFModule
from ..utils import *
from ..module import MLP, BaseTrainingModule
from ..data import *
from ..trainer import train_model, TrainingConfigs

# %% auto 0
__all__ = ['CCHVAEConfigs', 'CCHVAE']

# %% ../../nbs/methods/06_cchvae.ipynb 4
class Encoder(hk.Module):
    def __init__(self, sizes):
        super().__init__()
        self.encoder = MLP(sizes[:-1], name="Encoder")
        self.encoded_size = sizes[-1]
    
    def __call__(self, x: Array, is_training: bool):
        mu_enc = hk.Sequential([
            self.encoder, hk.Linear(self.encoded_size, name='mu_z')
        ])(x)
        logvar_enc = hk.Sequential([
            self.encoder, hk.Linear(self.encoded_size, name='logvar_z')
        ])(x)
        return mu_enc, logvar_enc

class Decoder(hk.Module):
    def __init__(self, sizes, input_size):
        super().__init__()
        self.decoder = MLP(sizes, name="Decoder")
        self.input_size = input_size
    
    def __call__(self, z: Array, is_training: bool):
        mu_dec = self.decoder(z)
        # TODO: use batchnorm
        # mu_dec = hk.BatchNorm(True, True, 0.9)(mu_dec, is_training)
        mu_dec = hk.Linear(self.input_size, name='mu_x')(mu_dec)
        
        logvar_dec = self.decoder(z)
        # TODO: use batchnorm
        # logvar_dec = hk.BatchNorm(True, True, 0.9)(logvar_dec, is_training)
        logvar_dec = hk.Linear(self.input_size, name='logvar_x')(logvar_dec)

        return mu_dec, logvar_dec

# %% ../../nbs/methods/06_cchvae.ipynb 5
class CHVAEConfigs(BaseParser):
    enc_sizes: List[int] = [20, 16, 14, 12, 5]
    dec_sizes: List[int] = [12, 14, 16, 20]
    lr = 0.001

# %% ../../nbs/methods/06_cchvae.ipynb 6
class CHVAE(BaseTrainingModule):
    def __init__(self, m_config: Dict):
        self.save_hyperparameters(m_config)
        self.m_config = validate_configs(m_config, CHVAEConfigs)
        self.opt = optax.adam(self.m_config.lr)

    def init_net_opt(self, dm, key):
        X, _ = dm.train_dataset[:128]
        encoded_size = self.m_config.enc_sizes[-1]
        Z = jnp.ones((X.shape[0], encoded_size))

        self.encoder = make_hk_module(
            Encoder, sizes=self.m_config.enc_sizes, 
        )
        self.decoder = make_hk_module(
            Decoder, sizes=self.m_config.dec_sizes,
            input_size=X.shape[-1]
        )

        enc_params = self.encoder.init(key, X, is_training=True)
        dec_params = self.decoder.init(key, Z, is_training=True)
        opt_state = self.opt.init((enc_params, dec_params))
        return (enc_params, dec_params), opt_state
    
    @partial(jax.jit, static_argnums=(0,))
    def encode(self, enc_params, rng_key, x):
        mu_z, logvar_z = self.encoder.apply(enc_params, rng_key, x, is_training=True)
        return mu_z, logvar_z
        
    @partial(jax.jit, static_argnums=(0,))
    def __reparameterize(self, rng_key, mu, logvar):
        std = jnp.exp(0.5 * logvar)
        eps = jax.random.normal(rng_key, std.shape)
        return mu + eps * std
    
    @partial(jax.jit, static_argnums=(0,))
    def decode(self, dec_params, rng_key, z):
        mu_x, logvar_x = self.decoder.apply(dec_params, rng_key, z, is_training=True)
        return mu_x, logvar_x
    
    @partial(jax.jit, static_argnums=(0,))
    def forward(self, params, rng_key, x):
        enc_params, dec_params = params
        keys = jax.random.split(rng_key, 3)
        mu_z, logvar_z = self.encode(enc_params, keys[0], x)
        z_rep = self.__reparameterize(keys[1], mu_z, logvar_z)
        mu_x, logvar_x = self.decode(dec_params, keys[2], z_rep)
        return mu_x, logvar_x, mu_z, logvar_z, z_rep
    
    @partial(jax.jit, static_argnums=(0,))
    def loss(self, params, rng_key, x):
        mu_x, logvar_x, mu_z, logvar_z, z_rep = self.forward(params, rng_key, x)
        recon_loss = jnp.mean(optax.l2_loss(mu_x, x))
        # kl_loss = -0.5 * jnp.sum(1 + logvar_z - mu_z**2 - jnp.exp(logvar_z))
        kl_loss = -0.5 * jnp.sum(1 + logvar_z - jnp.power(mu_z, 2) - jnp.exp(logvar_z))
        loss = recon_loss + kl_loss
        return loss

    @partial(jax.jit, static_argnums=(0,))
    def _training_step(
        self, 
        params: Tuple[hk.Params, hk.Params],
        opt_state: optax.OptState, 
        rng_key: random.PRNGKey, 
        batch: Tuple[jnp.array, jnp.array]
    ) -> Tuple[hk.Params, optax.OptState]:
        loss, grads = jax.value_and_grad(self.loss)(
            params, rng_key, batch[0])
        update_params, opt_state = grad_update(
            grads, params, opt_state, self.opt)
        return update_params, opt_state, loss

    def training_step(
        self,
        params: Tuple[hk.Params, hk.Params],
        opt_state: optax.OptState,
        rng_key: random.PRNGKey,
        batch: Tuple[jnp.array, jnp.array]
    ) -> Tuple[hk.Params, optax.OptState]:
        params, opt_state, loss = self._training_step(params, opt_state, rng_key, batch)
        self.log_dict({'train/loss': loss.item()})
        return params, opt_state
    
    def validation_step(
        self,
        params: Tuple[hk.Params, hk.Params],
        rng_key: random.PRNGKey,
        batch: Tuple[jnp.array, jnp.array],
    ) -> Tuple[hk.Params, optax.OptState]:
        loss = self.loss(params, rng_key, batch[0])
        self.log_dict({'val/loss': loss.item()})


# %% ../../nbs/methods/06_cchvae.ipynb 7
def _hyper_sphere_coordindates(
    rng_key: jrand.PRNGKey, # Random number generator key
    x: Array, # Input instance with only continuous features. Shape: (1, n_features)
    n_samples: int,
    high: float, # Upper bound
    low: float, # Lower bound
    p_norm: int = 2 # Norm
):
    key_1, key_2 = jrand.split(rng_key)
    delta = jrand.normal(key_1, shape=(n_samples, x.shape[-1]))
    dist = jrand.normal(key_2, shape=(n_samples,)) * (high - low) + low
    norm_p = jnp.linalg.norm(delta, ord=p_norm, axis=1)
    d_norm = jnp.divide(dist, norm_p).reshape(-1, 1)  # rescale/normalize factor
    delta = jnp.multiply(delta, d_norm)
    candidates = x + delta
    return candidates

# %% ../../nbs/methods/06_cchvae.ipynb 8
@auto_reshaping('x')
def _cchvae_generate(
    x: Array,
    rng_key: random.PRNGKey,
    pred_fn: Callable,
    max_steps: int,
    n_search_samples: int,
    step_size: float,
    cchvae_module: CHVAE,
    cchvae_params: Tuple[hk.Params, hk.Params],
    apply_fn: Callable,
):
    @jit
    def cond_fn(state):
        count, cf, _ = state
        return jnp.logical_and(count < max_steps, jnp.array_equal(x, cf))
    
    @jit
    def body_fn(state):
        count, candidate_cf, rng = state
        rng_key, subkey_1, subkey_2 = jrand.split(rng, num=3)
        low, high = step_size * count, step_size * (count + 1)
        # STEP 1 -- SAMPLE POINTS on hyper sphere around instance
        latent_neighbors = _hyper_sphere_coordindates(
            subkey_1, z_rep, n_search_samples, high=high, low=low, p_norm=1
        )
        x_ce, _ = cchvae_module.decode(cchvae_params[1], subkey_2, latent_neighbors)
        x_ce = apply_fn(x, x_ce.reshape(1, -1), hard=True)
        
        # STEP 2 -- COMPUTE l1 norms
        distances = jnp.abs(x_ce - x).sum(axis=1)

        # STEP 3 -- SELECT POINT with MINIMUM l1 norm
        y_candidates = pred_fn(x_ce).round().reshape(-1)
        indices = jnp.where(y_candidates != y_pred, 1, 0).astype(bool)
        distances = jnp.where(indices, distances, jnp.inf)
        
        candidate_cf = lax.cond(
            jnp.any(indices),
            lambda _: x_ce[jnp.argmin(distances)].reshape(1, -1),
            lambda _: candidate_cf,
            None
        )

        count += 1
        return count, candidate_cf, rng_key
    
    y_pred = pred_fn(x).round().reshape(-1)
    z, _ = cchvae_module.encode(cchvae_params[0], rng_key, x)
    # z_rep = jnp.repeat(z.reshape(1, -1), n_search_samples, axis=0)
    z_rep = z.reshape(1, -1)
    rng_key, _ = jrand.split(rng_key)
    state = (0, x, rng_key) # (count, candidate_cf, rng_key)
    count, candidate_cf, rng_key = jax.lax.while_loop(cond_fn, body_fn, state)
    # while cond_fn(state):
    #     count, candidate_cf, rng_key = body_fn(state)
    # print(count)
    return candidate_cf

# %% ../../nbs/methods/06_cchvae.ipynb 9
class CCHVAEConfigs(BaseParser):
    enc_sizes: List[int] = Field(
        [20, 16, 14, 12], description="Encoder hidden sizes"
    ) 
    dec_sizes: List[int] = Field(
        [12, 14, 16, 20], description="Decoder hidden sizes"
    )
    encoded_size: int = Field(5, description="Encoded size")
    lr: float = Field(0.001, description="Learning rate")
    max_steps: int = Field(1000, description="Max steps")
    n_search_samples: int = Field(300, description="Number of generated candidate counterfactuals.")
    step_size: float = Field(0.1, description="Step size")
    seed: int = Field(0, description="Seed for random number generator")

# %% ../../nbs/methods/06_cchvae.ipynb 10
class CCHVAE(BaseCFModule, BaseParametricCFModule):
    params: Tuple[hk.Params, hk.Params] = None
    module: CHVAE
    name: str = 'C-CHVAE'

    def __init__(self, m_config: Dict | CCHVAEConfigs = None):
        if m_config is None:
            m_config = CCHVAEConfigs()
        self.m_config = m_config
        self.module = CHVAE(m_config.dict())
        self.rng_key = random.PRNGKey(self.m_config.seed)

    def _is_module_trained(self) -> bool:
        return not (self.params is None)
    
    def train(
        self, 
        datamodule: TabularDataModule, # data module
        t_configs: TrainingConfigs | dict = None, # training configs
        *args, **kwargs
    ):
        _default_t_configs = dict(
            n_epochs=10, batch_size=128
        )
        if t_configs is None: t_configs = _default_t_configs
        params, _ = train_model(self.module, datamodule, t_configs)
        self.params = params

    def generate_cf(self, x: Array, pred_fn: Callable = None) -> jnp.ndarray:
        _cchvae_generate_fn_partial = partial(
            _cchvae_generate,
            pred_fn=pred_fn,
            max_steps=self.m_config.max_steps,
            n_search_samples=self.m_config.n_search_samples,
            step_size=self.m_config.step_size,
            cchvae_module=self.module,
            cchvae_params=self.params,
            apply_fn=self.data_module.apply_constraints,
        )
        return _cchvae_generate_fn_partial(x, self.rng_key)
    
    def generate_cfs(self, X: Array, pred_fn: Callable = None) -> jnp.ndarray:
        _cchvae_generate_fn_partial = partial(
            _cchvae_generate,
            pred_fn=pred_fn,
            max_steps=self.m_config.max_steps,
            n_search_samples=self.m_config.n_search_samples,
            step_size=self.m_config.step_size,
            cchvae_module=self.module,
            cchvae_params=self.params,
            apply_fn=self.data_module.apply_constraints,
        )
        rngs = lax.broadcast(self.rng_key, (X.shape[0], ))
        return jax.vmap(_cchvae_generate_fn_partial)(X, rngs)
        # for i in tqdm(range(X.shape[0])):
        #     rng = random.PRNGKey(i)
        #     cf = _cchvae_generate_fn_partial(X[i], rng)
        #     if i == 0:
        #         cfs = cf
        #     else:
        #         cfs = jnp.concatenate([cfs, cf], axis=0)
        # return cfs
