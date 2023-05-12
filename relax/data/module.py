# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/01_data.module.ipynb.

# %% ../../nbs/01_data.module.ipynb 3
from __future__ import annotations
from ..import_essentials import *
from ..utils import load_json, validate_configs, cat_normalize
from sklearn.preprocessing import StandardScaler, MinMaxScaler, OneHotEncoder
from sklearn.base import TransformerMixin
from sklearn.utils.validation import check_is_fitted, NotFittedError
from urllib.request import urlretrieve
from .loader import Dataset, ArrayDataset, DataLoader, DataloaderBackends
from pydantic.fields import ModelField

# %% auto 0
__all__ = ['BaseDataModule', 'find_imutable_idx_list', 'TransformerMixinType', 'TabularDataModuleConfigs', 'TabularDataModule',
           'sample', 'load_data']

# %% ../../nbs/01_data.module.ipynb 6
class BaseDataModule(ABC):
    """DataModule Interface"""

    @property
    @abstractmethod
    def data_name(self) -> str: 
        return
        
    @property
    @abstractmethod
    def data(self) -> Any:
        return
    
    @property
    @abstractmethod
    def train_dataset(self) -> Dataset:
        return
    
    @property
    @abstractmethod
    def val_dataset(self) -> Dataset:
        return

    @property
    @abstractmethod
    def test_dataset(self) -> Dataset:
        return

    def dataset(self, name: str) -> Dataset:
        raise NotImplementedError

    def train_dataloader(self, batch_size):
        raise NotImplementedError

    def val_dataloader(self, batch_size):
        raise NotImplementedError

    def test_dataloader(self, batch_size):
        raise NotImplementedError

    @abstractmethod
    def prepare_data(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def transform(self, data) -> jnp.DeviceArray:
        raise NotImplementedError

    @abstractmethod
    def inverse_transform(self, x: jnp.DeviceArray) -> Any:
        raise NotImplementedError

    def apply_constraints(
        self, 
        x: jnp.DeviceArray,
        cf: jnp.DeviceArray,
        hard: bool
    ) -> jnp.DeviceArray:
        return cf
    
    def apply_regularization(
        self, 
        x: jnp.DeviceArray,
        cf: jnp.DeviceArray,
        hard: bool
    ):
        raise NotImplementedError


# %% ../../nbs/01_data.module.ipynb 8
def find_imutable_idx_list(
    imutable_col_names: List[str],
    discrete_col_names: List[str],
    continuous_col_names: List[str],
    cat_arrays: List[List[str]],
) -> List[int]:
    imutable_idx_list = []
    for idx, col_name in enumerate(continuous_col_names):
        if col_name in imutable_col_names:
            imutable_idx_list.append(idx)

    cat_idx = len(continuous_col_names)

    for i, (col_name, cols) in enumerate(zip(discrete_col_names, cat_arrays)):
        cat_end_idx = cat_idx + len(cols)
        if col_name in imutable_col_names:
            imutable_idx_list += list(range(cat_idx, cat_end_idx))
        cat_idx = cat_end_idx
    return imutable_idx_list

# %% ../../nbs/01_data.module.ipynb 9
class TransformerMixinType(TransformerMixin):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, TransformerMixin):
            raise TypeError("`sklearn.base.TransformerMixin` required")
        return v
    
    @classmethod
    def __modify_schema__(
        cls, field_schema: Dict[str, Any], field: Optional[ModelField]
    ):
        if field:
            field_schema['type'] = 'TransformerMixin'


# %% ../../nbs/01_data.module.ipynb 10
def _supported_backends(): 
    back = DataloaderBackends()
    return back.supported()

class TabularDataModuleConfigs(BaseParser):
    """Configurator of `TabularDataModule`."""

    data_dir: str = Field(description="The directory of dataset.")
    data_name: str = Field(description="The name of `TabularDataModule`.")
    continous_cols: List[str] = Field(
        [], description="Continuous features/columns in the data."
    )
    discret_cols: List[str] = Field(
        [], description="Categorical features/columns in the data."
    )
    imutable_cols: List[str] = Field(
        [], description="Immutable features/columns in the data."
    )
    normalizer: Optional[TransformerMixinType] = Field(
        default_factory=lambda: MinMaxScaler(),
        description="Sklearn scalar for continuous features. Can be unfitted, fitted, or None. "
        "If not fitted, the `TabularDataModule` will fit using the training data. If fitted, no fitting will be applied. "
        "If `None`, no transformation will be applied. Default to `MinMaxScaler()`."
    )
    encoder: Optional[TransformerMixinType] = Field(
        default_factory=lambda: OneHotEncoder(sparse=False),
        description="Fitted encoder for categorical features. Can be unfitted, fitted, or None. "
        "If not fitted, the `TabularDataModule` will fit using the training data. If fitted, no fitting will be applied. "
        "If `None`, no transformation will be applied. Default to `OneHotEncoder(sparse=False)`."
    )
    sample_frac: Optional[float] = Field(
        None, description="Sample fraction of the data. Default to use the entire data.", 
        ge=0., le=1.0
    )
    backend: str = Field(
        "jax", description=f"`Dataloader` backend. Currently supports: {_supported_backends()}"
    )

    class Config:
        json_encoders = {
            TransformerMixinType: lambda v: f"{v.__class__.__name__}()",
        }

# %% ../../nbs/01_data.module.ipynb 13
def _check_cols(data: pd.DataFrame, configs: TabularDataModuleConfigs) -> pd.DataFrame:
    data = data.astype({
        col: float for col in configs.continous_cols
    })
    
    cols = configs.continous_cols + configs.discret_cols
    # check target columns
    target_col = data.columns[-1]
    assert not target_col in cols, \
        f"continous_cols or discret_cols contains target_col={target_col}."
    
    # check imutable cols
    for col in configs.imutable_cols:
        assert col in cols, \
            f"imutable_cols=[{col}] is not specified in `continous_cols` or `discret_cols`."
    data = data[cols + [target_col]]
    return data


# %% ../../nbs/01_data.module.ipynb 14
def _process_data(
    df: pd.DataFrame | None, configs: TabularDataModuleConfigs
) -> pd.DataFrame:
    if df is None:
        df = pd.read_csv(configs.data_dir)
    elif isinstance(df, pd.DataFrame):
        df = df
    else:
        raise ValueError(
            f"{type(df).__name__} is not supported as an input type for `TabularDataModule`.")

    df = _check_cols(df, configs)
    return df

# %% ../../nbs/01_data.module.ipynb 16
def _transform_df(
    transformer: TransformerMixin | None,
    data: pd.DataFrame,
    cols: List[str] | None,
):
    if transformer is None:
        return data[cols].to_numpy() if cols else np.array([[] for _ in range(len(data))])
    else:
        return (
            transformer.transform(data[cols])
                if cols else np.array([[] for _ in range(len(data))])
        )

# %% ../../nbs/01_data.module.ipynb 18
def _inverse_transform_np(
    transformer: TransformerMixin | None,
    x: np.ndarray,
    cols: List[str] | None
):
    assert len(cols) <= x.shape[-1], \
        f"x.shape={x.shape} probably will not match len(cols)={len(cols)}"
    
    if cols:
        data = transformer.inverse_transform(x) if transformer else x
        df = pd.DataFrame(data=data, columns=cols)
    else:
        df = None
    return df


# %% ../../nbs/01_data.module.ipynb 20
def _init_scalar_encoder(
    data: pd.DataFrame,
    configs: TabularDataModuleConfigs
) -> Dict[str, TransformerMixin | None]: 
    # The normlizer and encoder will be either None, fitted or not fitted.
    # If the user has specified the normlizer and encoder, then we will use it.
    # Otherwise, we will fit the normlizer and encoder.
    # fit scalar
    if configs.normalizer is not None:
        scalar = configs.normalizer
        try:
            check_is_fitted(scalar)
        except NotFittedError:
            if configs.continous_cols:  scalar.fit(data[configs.continous_cols])
            else:                       scalar = None
    else:
        scalar = None
    
    if configs.encoder is not None:
        encoder = configs.encoder
        try:
            check_is_fitted(encoder)
        except NotFittedError:
            if configs.discret_cols:    encoder.fit(data[configs.discret_cols])
            else:                       encoder = None
    else:
        encoder = None
    return dict(scalar=scalar, encoder=encoder)


# %% ../../nbs/01_data.module.ipynb 22
class TabularDataModule(BaseDataModule):
    """DataModule for tabular data"""
    cont_scalar = None # scalar for normalizing continuous features
    cat_encoder = None # encoder for encoding categorical features
    __initialized = False

    def __init__(
        self, 
        data_config: dict | TabularDataModuleConfigs, # Configurator of `TabularDataModule`
        data: pd.DataFrame = None # Data in `pd.DataFrame`. If `data` is `None`, the DataModule will load data from `data_dir`.
    ):
        self._configs: TabularDataModuleConfigs = validate_configs(
            data_config, TabularDataModuleConfigs
        )
        self._data = _process_data(data, self._configs)
        # init idx lists
        self.cat_idx = len(self._configs.continous_cols)
        self._imutable_idx_list = []
        self.prepare_data()

    def prepare_data(self):
        scalar_encoder_dict = _init_scalar_encoder(
            data=self._data, configs=self._configs
        )
        self.cont_scalar = scalar_encoder_dict['scalar']
        self.cat_encoder = scalar_encoder_dict['encoder']
        X, y = self.transform(self.data)

        self._cat_arrays = self.cat_encoder.categories_ \
            if self._configs.discret_cols else []

        self._imutable_idx_list = find_imutable_idx_list(
            imutable_col_names=self._configs.imutable_cols,
            discrete_col_names=self._configs.discret_cols,
            continuous_col_names=self._configs.continous_cols,
            cat_arrays=self._cat_arrays,
        )
        
        # prepare train & test
        train_test_tuple = train_test_split(X, y, shuffle=False)
        train_X, test_X, train_y, test_y = map(
             lambda x: x.astype(float), train_test_tuple
         )
        if self._configs.sample_frac:
            train_size = int(len(train_X) * self._configs.sample_frac)
            train_X, train_y = train_X[:train_size], train_y[:train_size]
        
        self._train_dataset = ArrayDataset(train_X, train_y)
        self._val_dataset = ArrayDataset(test_X, test_y)
        self._test_dataset = self.val_dataset

        self.__initialized = True

    def __setattr__(self, attr: str, val: Any) -> None:
        if self.__initialized and attr in (
            '_data', 'cat_idx', '_imutable_idx_list', '_cat_arrays',
            '_train_dataset', '_val_dataset', '_test_dataset',
            'cont_scalar', 'cat_encoder'
        ):
            raise ValueError(f'{attr} attribute should not be set after '
                             f'{self.__class__.__name__} is initialized')

        super().__setattr__(attr, val)

    @property
    def data_name(self) -> str: 
        return self._configs.data_name
    
    @property
    def data(self) -> pd.DataFrame:
        """Loaded data in `pd.DataFrame`."""
        return self._data
    
    @property
    def train_dataset(self) -> ArrayDataset:
        return self._train_dataset
    
    @property
    def val_dataset(self) -> ArrayDataset:
        return self._val_dataset

    @property
    def test_dataset(self) -> ArrayDataset:
        return self._test_dataset

    def dataset(
        self, name: str # Name of the dataset; should be one of ['train', 'val', 'test'].
    ) -> ArrayDataset:
        if name == 'train': return self._train_dataset
        elif name == 'val': return self._val_dataset
        elif name == 'test': return self._test_dataset
        else: raise ValueError(f"`name` must be one of ['train', 'val', 'test'], but got {name}")

    def train_dataloader(self, batch_size):
        return DataLoader(self.train_dataset, self._configs.backend, 
            batch_size=batch_size, shuffle=True, num_workers=0, drop_last=False
        )

    def val_dataloader(self, batch_size):
        return DataLoader(self.val_dataset, self._configs.backend,
            batch_size=batch_size, shuffle=True, num_workers=0, drop_last=False
        )

    def test_dataloader(self, batch_size):
        return DataLoader(self.val_dataset, self._configs.backend,
            batch_size=batch_size, shuffle=True, num_workers=0, drop_last=False
        )

    def transform(
        self, 
        data: pd.DataFrame, # Data to be transformed to `numpy.ndarray`
    ) -> Tuple[np.ndarray, np.ndarray]: # Return `(X, y)`
        """Transform data into numerical representations."""
        # TODO: validate `data`
        X_cont = _transform_df(
            self.cont_scalar, data, self._configs.continous_cols
        )
        X_cat = _transform_df(
            self.cat_encoder, data, self._configs.discret_cols
        )
        X = np.concatenate((X_cont, X_cat), axis=1)
        y = data.iloc[:, -1:].to_numpy()
        
        return X, y

    def inverse_transform(
        self, 
        x: jnp.DeviceArray, # The transformed input to be scaled back
        y: jnp.DeviceArray = None # The transformed label to be scaled back. If `None`, the target columns will not be scaled back.
    ) -> pd.DataFrame: # Transformed `pd.DataFrame`. 
        """Scaled back into `pd.DataFrame`."""
        X_cont_df = _inverse_transform_np(
            self.cont_scalar, x[:, :self.cat_idx], self._configs.continous_cols
        )
        X_cat_df = _inverse_transform_np(
            self.cat_encoder, x[:, self.cat_idx:], self._configs.discret_cols
        )
        if y is not None:
            y_df = pd.DataFrame(data=y, columns=[self.data.columns[-1]])
        else:
            y_df = None
        
        return pd.concat(
            [X_cont_df, X_cat_df, y_df], axis=1
        )

    def apply_constraints(
        self, 
        x: jnp.DeviceArray, # input
        cf: jnp.DeviceArray, # Unnormalized counterfactuals
        hard: bool = False # Apply hard constraints or not
    ) -> jnp.DeviceArray:
        """Apply categorical normalization and immutability constraints"""
        cf = cat_normalize(
            cf, cat_arrays=self._cat_arrays, 
            cat_idx=len(self._configs.continous_cols),
            hard=hard
        )
        # apply immutable constraints
        if len(self._configs.imutable_cols) > 0:
            cf = cf.at[:, self._imutable_idx_list].set(x[:, self._imutable_idx_list])
        return cf

    def apply_regularization(
        self, 
        x: jnp.DeviceArray, # Input
        cf: jnp.DeviceArray, # Unnormalized counterfactuals
    ) -> float: # Return regularization loss
        """Apply categorical constraints by adding regularization terms"""
        reg_loss = 0.
        cat_idx = len(self._configs.continous_cols)

        for col in self._cat_arrays:
            cat_idx_end = cat_idx + len(col)
            reg_loss += jnp.power(
                (jnp.sum(cf[cat_idx:cat_idx_end]) - 1.0), 2
            )
        return reg_loss


# %% ../../nbs/01_data.module.ipynb 43
def sample(datamodule: BaseDataModule, frac: float = 1.0): 
    X, y = datamodule.train_dataset[:]
    size = int(len(X) * frac)
    return X[:size], y[:size]

# %% ../../nbs/01_data.module.ipynb 47
DEFAULT_DATA_CONFIGS = {
    'adult': {
        'data' :'assets/adult/data.csv',
        'conf' :'assets/adult/configs.json',
        'model' :'assets/adult/model'
    },
    'heloc': {
        'data': 'assets/heloc/data.csv',
        'conf': 'assets/heloc/configs.json',
        'model' :'assets/heloc/model'
    },
    'oulad': {
        'data': 'assets/oulad/data.csv',
        'conf': 'assets/oulad/configs.json',
        'model' :'assets/oulad/model'
    },
    'credit': {
        'data': 'assets/credit/data.csv',
        'conf': 'assets/credit/configs.json',
        'model' :'assets/credit/model'
    },
    'cancer': {
        'data': 'assets/cancer/data.csv',
        'conf': 'assets/cancer/configs.json',
        'model' :'assets/cancer/model'
    },
    'student_performance': {
        'data': 'assets/student_performance/data.csv',
        'conf': 'assets/student_performance/configs.json',
        'model' :'assets/student_performance/model'
    },
    'titanic': {
        'data': 'assets/titanic/data.csv',
        'conf': 'assets/titanic/configs.json',
        'model' :'assets/titanic/model'
    },
    'german': {
        'data': 'assets/german/data.csv',
        'conf': 'assets/german/configs.json',
        'model' :'assets/german/model'
    },
    'spam': {
        'data': 'assets/spam/data.csv',
        'conf': 'assets/spam/configs.json',
        'model' :'assets/spam/model'
    },
    'ozone': {
        'data': 'assets/ozone/data.csv',
        'conf': 'assets/ozone/configs.json',
        'model' :'assets/ozone/model'
    },
    'qsar': {
        'data': 'assets/qsar/data.csv',
        'conf': 'assets/qsar/configs.json',
        'model' :'assets/qsar/model'
    },
    'bioresponse': {
        'data': 'assets/bioresponse/data.csv',
        'conf': 'assets/bioresponse/configs.json',
        'model' :'assets/bioresponse/model'
    },
    'churn': {
        'data': 'assets/churn/data.csv',
        'conf': 'assets/churn/configs.json',
        'model' :'assets/churn/model'
    },
    'road': {
        'data': 'assets/road/data.csv',
        'conf': 'assets/road/configs.json',
        'model' :'assets/road/model'
    }
}

# %% ../../nbs/01_data.module.ipynb 48
def _validate_dataname(data_name: str):
    if data_name not in DEFAULT_DATA_CONFIGS.keys():
        raise ValueError(f'`data_name` must be one of {DEFAULT_DATA_CONFIGS.keys()}, '
            f'but got data_name={data_name}.')

# %% ../../nbs/01_data.module.ipynb 49
def load_data(
    data_name: str, # The name of data
    return_config: bool = False, # Return `data_config `or not
    data_configs: dict = None # Data configs to override default configuration
) -> TabularDataModule | Tuple[TabularDataModule, TabularDataModuleConfigs]: 
    """High-level util function for loading `data` and `data_config`."""
    
    _validate_dataname(data_name)

    # get data/config/model urls
    _data_path = DEFAULT_DATA_CONFIGS[data_name]['data']
    _conf_path = DEFAULT_DATA_CONFIGS[data_name]['conf']
    _model_path = DEFAULT_DATA_CONFIGS[data_name]['model']
    
    data_url = f"https://github.com/BirkhoffG/ReLax/raw/master/{_data_path}"
    conf_url = f"https://github.com/BirkhoffG/ReLax/raw/master/{_conf_path}"
    model_params_url = f"https://github.com/BirkhoffG/ReLax/raw/master/{_model_path}/params.npy"
    model_tree_url = f"https://github.com/BirkhoffG/ReLax/raw/master/{_model_path}/tree.pkl"

    # create new dir
    data_dir = Path(os.getcwd()) / "cf_data"
    if not data_dir.exists():
        os.makedirs(data_dir)
    data_path = data_dir / data_name / 'data.csv'
    conf_path = data_dir / data_name / 'configs.json'
    model_path = data_dir / data_name / "model"
    if not model_path.exists():
        os.makedirs(model_path)

    # download data/configs and trained model
    if not data_path.is_file():
        urlretrieve(data_url, data_path)    
    if not conf_path.is_file():
        urlretrieve(conf_url, conf_path)
    params_path = os.path.join(model_path, "params.npy")
    tree_path = os.path.join(model_path, "tree.pkl")
    if not (os.path.isfile(params_path) and os.path.isfile(tree_path)):
        urlretrieve(model_params_url, params_path)
        urlretrieve(model_tree_url, tree_path)

    # read config
    config = load_json(conf_path)['data_configs']
    config['data_dir'] = str(data_path)

    if not (data_configs is None):
        config.update(data_configs)

    config = TabularDataModuleConfigs(**config)
    data_module = TabularDataModule(config)

    if return_config:
        return data_module, config
    else:
        return data_module

