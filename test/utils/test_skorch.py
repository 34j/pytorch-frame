import pandas as pd
import pytest
import torch.nn as nn

from torch_frame import TaskType, stype
from torch_frame.config.text_embedder import TextEmbedderConfig
from torch_frame.data.dataset import Dataset
from torch_frame.datasets.fake import FakeDataset
from torch_frame.nn.models.mlp import MLP
from torch_frame.testing.text_embedder import HashTextEmbedder
from torch_frame.utils.skorch import NeuralNetBinaryClassifierPytorchFrame, NeuralNetClassifierPytorchFrame
import torch.nn.functional as F
class BCEWithLogitsLossSigmoidSqueeze(nn.BCEWithLogitsLoss):
    def forward(self, input, target):
        # float to long
        input = F.sigmoid(input).long()
        return super().forward(input.squeeze(), target.long())

@pytest.mark.parametrize('cls', ["mlp"])
@pytest.mark.parametrize(
    'stypes',
    [
        [stype.numerical],
        [stype.categorical],
        # [stype.text_embedded],
        # [stype.numerical, stype.numerical, stype.text_embedded],
    ])
@pytest.mark.parametrize('task_type_and_loss_cls', [
    (TaskType.REGRESSION, nn.MSELoss),
    # (TaskType.BINARY_CLASSIFICATION, BCEWithLogitsLossSqueeze),
    (TaskType.MULTICLASS_CLASSIFICATION, nn.CrossEntropyLoss),
])
@pytest.mark.parametrize('pass_dataset', [False])
def test_skorch_torchframe_dataset(cls, stypes, task_type_and_loss_cls,
                                   pass_dataset: bool):
    task_type, loss_cls = task_type_and_loss_cls
    loss = loss_cls()

    # initialize dataset
    dataset: Dataset = FakeDataset(
        num_rows=30,
        # with_nan=True,
        stypes=stypes,
        create_split=True,
        task_type=task_type,
        col_to_text_embedder_cfg=TextEmbedderConfig(
            text_embedder=HashTextEmbedder(8)),
    )
    dataset.materialize()
    train_dataset, val_dataset, test_dataset = dataset.split()
    # print(dataset.col_stats)
    # # convert to dataframe
    # col_to_stype = dataset.col_to_stype
    # # remove split_col and target_col
    # col_to_stype = {
    #     k: v
    #     for k, v in col_to_stype.items()
    #     if k not in [dataset.split_col, dataset.target_col]
    # }
    if not pass_dataset:
        df_train = pd.concat([train_dataset.df, val_dataset.df])
        X_train, y_train = df_train.drop(
            columns=[dataset.target_col, dataset.split_col]), df_train[
                dataset.target_col]
        df_test = test_dataset.df
        X_test, y_test = df_test.drop(
            columns=[dataset.target_col, dataset.split_col]), df_test[
                dataset.target_col]

        # never use dataset again
        # we assume that only dataframes are available
        # del dataset, train_dataset, val_dataset, test_dataset

    if cls == "mlp":
        channels = 8
        out_channels = dataset.num_classes if task_type == TaskType.MULTICLASS_CLASSIFICATION else 1
        num_layers = 3
        model = MLP(
            channels=channels,
            out_channels=out_channels,
            num_layers=num_layers,
            col_stats=dataset.col_stats,
            col_names_dict=dataset.tensor_frame.col_names_dict,
            normalization="layer_norm",
        )
    else:
        raise NotImplementedError

    if task_type in [TaskType.REGRESSION, TaskType.MULTICLASS_CLASSIFICATION]:
        net = NeuralNetClassifierPytorchFrame(
            module=model,
            criterion=loss,
            max_epochs=2,
            # lr=args.lr,
            # device=device,
            verbose=1,
            batch_size=3,
            # col_to_stype=col_to_stype,
        )
    elif task_type == TaskType.BINARY_CLASSIFICATION:
        net = NeuralNetBinaryClassifierPytorchFrame(
            module=model,
            criterion=loss,
            max_epochs=2,
            # lr=args.lr,
            # device=device,
            verbose=1,
            batch_size=3,
            # col_to_stype=col_to_stype,
        )       
        
    if pass_dataset:
        net.fit(dataset)
        y_pred = net.predict(test_dataset)
    else:
        net.fit(X_train, y_train)
        y_pred = net.predict(X_test)
