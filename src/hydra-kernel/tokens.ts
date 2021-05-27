import { ICellModel } from '@jupyterlab/cells';
import { IObservableList } from '@jupyterlab/observables';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';

export interface IBindingModel {
  readonly name: string;
}

export interface ICellMetadata {
  hasBinding(cell: ICellModel): boolean;
  setBindingName(cell: ICellModel, name: string): void;
  removeBinding(cell: ICellModel): void;
  getBindingName(cell: ICellModel): string;
  onBindingNameChanged(cell: ICellModel, fn: () => void): void;
}

export interface IBindingRegistry {
  register(kernel: IKernelConnection): IObservableList<IBindingModel>;
  unregister(kernel: IKernelConnection): void;
}

export interface IBindingManager {
  readonly model: IObservableList<IBindingModel>;
}
