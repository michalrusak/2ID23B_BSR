import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export interface PhotoState {
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  success: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class PhotoStateService {
  private initialState: PhotoState = {
    isUploading: false,
    uploadProgress: 0,
    error: null,
    success: null,
  };

  private state$ = new BehaviorSubject<PhotoState>(this.initialState);

  getState() {
    return this.state$.asObservable();
  }

  setUploading(isUploading: boolean) {
    this.updateState({ isUploading });
  }

  setProgress(uploadProgress: number) {
    this.updateState({ uploadProgress });
  }

  setError(error: string | null) {
    this.updateState({ error, success: null });
  }

  setSuccess(success: string | null) {
    this.updateState({ success, error: null });
  }

  reset() {
    this.state$.next(this.initialState);
  }

  private updateState(partialState: Partial<PhotoState>) {
    this.state$.next({
      ...this.state$.value,
      ...partialState,
    });
  }
}
