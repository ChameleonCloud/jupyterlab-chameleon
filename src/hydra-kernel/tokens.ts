import { ICellModel } from '@jupyterlab/cells';
import { IObservableList } from '@jupyterlab/observables';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';
import { Token } from '@lumino/coreutils';

export interface IBindingModel {
  readonly name: string;
  readonly connection: IBindingModel.IConnection;
  readonly state: 'connected' | 'disconnected' | 'interrupted' | 'creating';
}

export declare namespace IBindingModel {
  interface IConnection {
    readonly host: string;
    readonly user?: string;
  }
}

export interface ICellMetadata {
  hasBinding(cell: ICellModel): boolean;
  setBindingName(cell: ICellModel, name: string): void;
  removeBinding(cell: ICellModel): void;
  getBindingName(cell: ICellModel): string;
  onBindingNameChanged(cell: ICellModel, fn: () => void): void;
}

export const IBindingRegistry = new Token<IBindingRegistry>(
  '@chameleoncloud/jupyter-chameleon:IBindingRegistry'
);

export interface IBindingRegistry {
  register(kernel: IKernelConnection): IObservableList<IBindingModel>;
  unregister(kernel: IKernelConnection): void;
  getBindings(kernel: IKernelConnection): IObservableList<IBindingModel>;
}
