# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_data.utils.ipynb.

# %% ../nbs/01_data.utils.ipynb 2
from __future__ import annotations
from fastcore.test import *
import pandas as pd
import numpy as np
import jax
import jax.numpy as jnp
import einops
import os, sys, json, pickle
import shutil
from .utils import *
import chex

# %% auto 0
__all__ = ['PREPROCESSING_TRANSFORMATIONS', 'DataPreprocessor', 'MinMaxScaler', 'EncoderPreprocessor', 'OrdinalPreprocessor',
           'OneHotEncoder', 'Transformation', 'MinMaxTransformation', 'OneHotTransformation', 'OrdinalTransformation',
           'IdentityTransformation', 'Feature', 'FeaturesList']

# %% ../nbs/01_data.utils.ipynb 5
def _check_xs(xs: np.ndarray, name: str):
    if xs.ndim > 2 or (xs.ndim == 2 and xs.shape[1] != 1):
        raise ValueError(f"`{name}` only supports array with a single feature, but got shape={xs.shape}.")
    
        
class DataPreprocessor:

    def __init__(
        self, 
        name: str = None # The name of the preprocessor. If None, the class name will be used.
    ):
        """Base class for data preprocessors."""
        self.name = name or self.__class__.__name__
    
    def fit(self, xs, y=None):
        """Fit the preprocessor with `xs` and `y`."""
        raise NotImplementedError
    
    def transform(self, xs):
        """Transform `xs`."""
        raise NotImplementedError
    
    def fit_transform(self, xs, y=None):
        """Fit the preprocessor with `xs` and `y`, then transform `xs`."""
        self.fit(xs, y)
        return self.transform(xs)
    
    def inverse_transform(self, xs):
        """Inverse transform `xs`."""
        raise NotImplementedError
    
    def to_dict(self) -> dict:
        """Convert the preprocessor to a dictionary."""
        raise NotImplementedError
    
    def from_dict(self, params: dict):
        """Load the attributes of the preprocessor from a dictionary."""
        raise NotImplementedError
        
    __ALL__ = ["fit", "transform", "fit_transform", "inverse_transform", "to_dict", "from_dict"]

# %% ../nbs/01_data.utils.ipynb 6
class MinMaxScaler(DataPreprocessor): 
    def __init__(self):
        super().__init__(name="minmax")
        
    def fit(self, xs, y=None):
        _check_xs(xs, name="MinMaxScaler")
        self.min_ = xs.min(axis=0)
        self.max_ = xs.max(axis=0)
        return self
    
    def transform(self, xs):
        return (xs - self.min_) / (self.max_ - self.min_)
    
    def inverse_transform(self, xs):
        return xs * (self.max_ - self.min_) + self.min_
    
    def from_dict(self, params: dict):
        self.min_ = params["min_"]
        self.max_ = params["max_"]
        return self
    
    def to_dict(self) -> dict:
        return {"min_": self.min_, "max_": self.max_}

# %% ../nbs/01_data.utils.ipynb 12
def _unique(xs):
    if xs.dtype == object:
        # Note: np.unique does not work with object dtype
        # We will enforce xs to be string type
        # It assumes that xs is a list of strings, and might not work
        # for other cases (e.g., list of string and numbers)
        return np.unique(xs.astype(str))
    return np.unique(xs)

# %% ../nbs/01_data.utils.ipynb 13
class EncoderPreprocessor(DataPreprocessor):
    """Encode categorical features as an integer array."""
    def _fit(self, xs, y=None):
        _check_xs(xs, name="EncoderPreprocessor")
        self.categories_ = _unique(xs)

    def _transform(self, xs):
        """Transform data to ordinal encoding."""
        if xs.dtype == object:
            xs = xs.astype(str)
        ordinal = np.searchsorted(self.categories_, xs)
        # return einops.rearrange(ordinal, 'k n -> n k')
        return ordinal
    
    def _inverse_transform(self, xs):
        """Transform ordinal encoded data back to original data."""
        return self.categories_[xs.T].T
    
    def from_dict(self, params: dict):
        self.categories_ = params["categories_"]
        return self
    
    def to_dict(self) -> dict:
        return {"categories_": self.categories_}

# %% ../nbs/01_data.utils.ipynb 14
class OrdinalPreprocessor(EncoderPreprocessor):
    """Ordinal encoder for a single feature."""
    
    def fit(self, xs, y=None):
        self._fit(xs, y)
        return self
    
    def transform(self, xs):
        if xs.ndim == 1:
            raise ValueError(f"OrdinalPreprocessor only supports 2D array with a single feature, "
                             f"but got shape={xs.shape}.")
        return self._transform(xs)
    
    def inverse_transform(self, xs):
        return self._inverse_transform(xs)

# %% ../nbs/01_data.utils.ipynb 16
class OneHotEncoder(EncoderPreprocessor):
    """One-hot encoder for a single categorical feature."""
    
    def fit(self, xs, y=None):
        self._fit(xs, y)
        return self

    def transform(self, xs):
        if xs.ndim == 1:
            raise ValueError(f"OneHotEncoder only supports 2D array with a single feature, "
                             f"but got shape={xs.shape}.")
        xs_int = self._transform(xs)
        one_hot_feats = jax.nn.one_hot(xs_int, len(self.categories_))
        return einops.rearrange(one_hot_feats, 'n k d -> n (k d)')

    def inverse_transform(self, xs):
        xs_int = np.argmax(xs, axis=-1)
        return self._inverse_transform(xs_int).reshape(-1, 1)

# %% ../nbs/01_data.utils.ipynb 19
class Transformation:
    def __init__(self, name, transformer):
        self.name = name
        self.transformer = transformer

    @property
    def is_categorical(self) -> bool:
        return isinstance(self.transformer, EncoderPreprocessor)

    def fit(self, xs, y=None):
        self.transformer.fit(xs)
        return self
    
    def transform(self, xs):
        return self.transformer.transform(xs)

    def fit_transform(self, xs, y=None):
        return self.transformer.fit_transform(xs)
    
    def inverse_transform(self, xs):
        return self.transformer.inverse_transform(xs)

    def apply_constraints(self, xs, cfs, hard: bool = False):
        return cfs
    
    def compute_reg_loss(self, xs, cfs, hard: bool = False):
        return 0.
    
    def from_dict(self, params: dict):
        self.name = params["name"]
        self.transformer.from_dict(params["transformer"])
        return self
    
    def to_dict(self) -> dict:
        return {"name": self.name, "transformer": self.transformer.to_dict()}

# %% ../nbs/01_data.utils.ipynb 20
class MinMaxTransformation(Transformation):
    def __init__(self):
        super().__init__("minmax", MinMaxScaler())

    def apply_constraints(self, xs, cfs, hard: bool = False):
        return jnp.clip(cfs, 0., 1.)

# %% ../nbs/01_data.utils.ipynb 22
class OneHotTransformation(Transformation):
    def __init__(self):
        super().__init__("ohe", OneHotEncoder())

    @property
    def num_categories(self) -> int:
        return len(self.transformer.categories_)

    def apply_constraints(self, xs, cfs, hard: bool = False):
        return jax.lax.cond(
            hard,
            true_fun=lambda x: jax.nn.one_hot(jnp.argmax(x, axis=-1), self.num_categories),
            false_fun=lambda x: jax.nn.softmax(x, axis=-1),
            operand=cfs,
        )
    
    def compute_reg_loss(self, xs, cfs, hard: bool = False):
        return (cfs.sum(axis=-1, keepdims=True) - 1.0) ** 2

# %% ../nbs/01_data.utils.ipynb 24
class OrdinalTransformation(Transformation):
    def __init__(self):
        super().__init__("ordinal", OrdinalPreprocessor())

    @property
    def num_categories(self) -> int:
        return len(self.transformer.categories_)
    
class IdentityTransformation(Transformation):
    def __init__(self):
        super().__init__("identity", None)

    def fit(self, xs, y=None):
        return self
    
    def transform(self, xs):
        return xs
    
    def fit_transform(self, xs, y=None):
        return xs

    def apply_constraints(self, xs, cfs, hard: bool = False):
        return cfs
    
    def to_dict(self):
        return {'name': 'identity'}
    
    def from_dict(self, params: dict):
        self.name = params["name"]
        return self

# %% ../nbs/01_data.utils.ipynb 26
class Feature:
    
    def __init__(
        self,
        name: str,
        data: np.ndarray,
        transformation: str | Transformation,
        transformed_data = None,
        is_immutable: bool = False,
        is_categorical: bool = None,
    ):
        self.name = name
        self.data = data
        if isinstance(transformation, str):
            self.transformation = PREPROCESSING_TRANSFORMATIONS[transformation]()
        elif isinstance(transformation, Transformation):
            self.transformation = transformation
        elif isinstance(transformation, dict):
            # TODO: only supported transformation can be used for serialization
            t_name = transformation['name']
            if t_name not in PREPROCESSING_TRANSFORMATIONS.keys():
                raise ValueError("Only supported transformation can be inited from dict. "
                                 f"Got {t_name}, but should be one of {PREPROCESSING_TRANSFORMATIONS.keys()}.")
            self.transformation = PREPROCESSING_TRANSFORMATIONS[t_name]().from_dict(transformation)
        else:
            raise ValueError(f"Unknown transformer {transformation}")
        self._transformed_data = transformed_data
        self.is_immutable = is_immutable
        if is_categorical is not None:
            self._is_categorical = is_categorical
            assert self._is_categorical == self.transformation.is_categorical
        else:
            self._is_categorical = self.transformation.is_categorical

    @property
    def is_categorical(self) -> bool:
        return self._is_categorical

    @property
    def transformed_data(self) -> jax.Array:
        if self._transformed_data is None:
            return self.fit_transform(self.data)
        else:
            return self._transformed_data

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
    
    def to_dict(self):
        return {
            'name': self.name,
            'data': self.data,
            'transformed_data': self.transformed_data,
            'transformation': self.transformation.to_dict(),
            'is_immutable': self.is_immutable,
            'is_categorical': self.is_categorical,
        }
    
    def __repr__(self):
        # return f"Feature(" \
        #        f"name={self.name}, \ndata={self.data}, \n" \
        #        f"transformed_data={self.transformed_data}, \n" \
        #        f"transformer={self.transformation}, \n" \
        #        f"is_immutable={self.is_immutable})"
        dict_repr = self.to_dict()
        return f"Feature(" + \
               f",\n".join([f"{k}={v}" for k, v in dict_repr.items()]) + f")"
    
    __str__ = __repr__

    def __get_item__(self, idx):
        return {
            'data': self.data[idx],
            'transformed_data': self.transformed_data[idx],
        }

    def fit(self):
        self.transformation.fit(self.data)
        return self
    
    def transform(self, xs):
        return self.transformation.transform(xs)

    def fit_transform(self, xs):
        return self.transformation.fit_transform(xs)
    
    def inverse_transform(self, xs):
        return self.transformation.inverse_transform(xs)
    
    def apply_constraints(self, xs, cfs, hard: bool = False):
        return jax.lax.cond(
            self.is_immutable,
            true_fun=lambda xs: jnp.broadcast_to(xs, cfs.shape),
            false_fun=lambda _: self.transformation.apply_constraints(xs, cfs, hard),
            operand=xs,
        )
    
    def compute_reg_loss(self, xs, cfs, hard: bool = False):
        return self.transformation.compute_reg_loss(xs, cfs, hard)

# %% ../nbs/01_data.utils.ipynb 27
PREPROCESSING_TRANSFORMATIONS = {
    'ohe': OneHotTransformation,
    'minmax': MinMaxTransformation,
    'ordinal': OrdinalTransformation,
    'identity': IdentityTransformation,
}

# %% ../nbs/01_data.utils.ipynb 30
class FeaturesList:
    def __init__(
        self,
        features: list[Feature] | FeaturesList,
        *args, **kwargs
    ):
        if isinstance(features, FeaturesList):
            self._features = features.features
            self._feature_indices = features.feature_indices
            self._transformed_data = features.transformed_data
        elif isinstance(features, Feature):
            self._features = [features]
        elif isinstance(features, list):
            if len(features) > 0 and not isinstance(features[0], Feature):
                raise ValueError(f"Invalid features type: {type(features[0]).__name__}")
            self._features = features
        else:
            raise ValueError(f"Unknown features type. Got {type(features).__name__}")
        
        # Record the current position of the features
        self.pose = 0

    # Iterator
    def __len__(self):
        return len(self._features)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.pose < len(self):
            feat = self._features[self.pose]
            self.pose += 1
            return feat
        else:
            self.pose = 0
            raise StopIteration

    @property
    def features(self) -> list[Feature]: # Return [Feature(...), ...]
        return self._features

    @property
    def feature_indices(self) -> list[tuple[int, int]]: # Return [(start, end), ...]
        if not hasattr(self, "_feature_indices") or self._feature_indices is None or len(self._feature_indices) == 0:
            self._transform_data()
        return self._feature_indices
    
    @property
    def features_and_indices(self) -> list[tuple[Feature, tuple[int, int]]]: # Return [(Feature(...), (start, end)), ...]
        return list(zip(self.features, self.feature_indices))
    
    @property
    def feature_name_indices(self) -> dict[str, tuple[int, int]]: # Return {feature_name: (feat_idx, start, end), ...}
        if not hasattr(self, "_feature_indices") or self._feature_indices is None:
            self._transform_data()
        return self._feature_name_indices
    
    @property
    def transformed_data(self):
        if not hasattr(self, "_transformed_data") or self._transformed_data is None:
            self._transform_data()
        return self._transformed_data
    
    def _transform_data(self):
        self._feature_indices = []
        self._feature_name_indices = {}
        self._transformed_data = []
        start, end = 0, 0
        for i, feat in enumerate(self.features):
            transformed_data = feat.transformed_data
            end += transformed_data.shape[-1]
            self._feature_indices.append((start, end))
            self._feature_name_indices[feat.name] = (i, start, end)
            self._transformed_data.append(transformed_data)
            start = end

        self._transformed_data = jnp.concatenate(self._transformed_data, axis=-1)
    
    def transform(self, data: dict[str, jax.Array]):
        if not isinstance(data, dict):
            raise ValueError(f"Invalid data type: {type(data).__name__}, should be dict[str, jax.Array]")

        transformed_data = [None] * len(self.features)
        for feat_name, val in data.items():
            feat_idx, _, _ = self.feature_name_indices[feat_name]
            feat = self.features[feat_idx]
            transformed_data[feat_idx] = feat.transform(val)
        return jnp.concatenate(transformed_data, axis=-1)

    def inverse_transform(self, xs) -> dict[str, jax.Array]:
        orignial_data = {}
        for feat, (start, end) in self.features_and_indices:
            orignial_data[feat.name] = feat.inverse_transform(xs[:, start:end])
        return orignial_data

    def apply_constraints(self, xs, cfs, hard: bool = False):
        constrainted_cfs = []
        for feat, (start, end) in self.features_and_indices:
            _cfs = feat.apply_constraints(xs[:, start:end], cfs[:, start:end], hard)
            constrainted_cfs.append(_cfs)
        return jnp.concatenate(constrainted_cfs, axis=-1)
    
    def compute_reg_loss(self, xs, cfs, hard: bool = False):
        reg_loss = 0.
        for feat, (start, end) in self.features_and_indices:
            reg_loss += feat.compute_reg_loss(xs[:, start:end], cfs[:, start:end], hard)
        return reg_loss

    def to_dict(self):
        return {
            'features': [feat.to_dict() for feat in self.features],
        }
    
    @classmethod
    def from_dict(cls, d):
        return cls(
            features=[Feature.from_dict(feat) for feat in d['features']],
        )
    
    def to_pandas(self, use_transformed: bool = False) -> pd.DataFrame:
        if use_transformed:
            data = {feat.name: feat.transformed_data.reshape(-1) for feat in self.features}
        else:
            data = {feat.name: feat.data.reshape(-1) for feat in self.features}
        return pd.DataFrame(data=data)

    def save(self, saved_dir):
        os.makedirs(saved_dir, exist_ok=True)
        save_pytree(self.to_dict(), saved_dir)
        
    @classmethod
    def load_from_path(cls, saved_dir):
        return cls.from_dict(load_pytree(saved_dir))
