import { ICellModel } from '@jupyterlab/cells';

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
