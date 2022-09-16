# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00a_inferfaces.ipynb.

# %% auto 0
__all__ = ['BaseCFExplanationModule', 'LocalCFExplanationModule']

# %% ../nbs/00a_inferfaces.ipynb 3
from .import_essentials import *
from .datasets import TabularDataModule
from copy import deepcopy

# %% ../nbs/00a_inferfaces.ipynb 4
class BaseCFExplanationModule(ABC):
    cat_arrays = []
    cat_idx = 0

    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def generate_cfs(
        self,
        X: chex.ArrayBatched,
        pred_fn: Optional[Callable] = None,
        params: Optional[hk.Params] = None,
        rng_key: Optional[random.PRNGKey] = None
    ) -> chex.ArrayBatched:
        pass

    def update_cat_info(self, data_module: TabularDataModule):
        self.cat_arrays = deepcopy(data_module.cat_arrays)
        self.cat_idx = data_module.cat_idx
        self.imutable_idx_list = data_module.imutable_idx_list

    # @abstractmethod
    # def generate_cf_results(
    #     self,
    #     dm: TabularDataModule,
    #     pred_fn: Optional[Callable] = None) -> CFExplanationResults:
    #     pass

# %% ../nbs/00a_inferfaces.ipynb 5
class LocalCFExplanationModule(BaseCFExplanationModule):
    pred_fn: Callable[[jnp.DeviceArray], jnp.DeviceArray]
