import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import {
  Observable,
  BehaviorSubject,
  tap,
  switchMap,
  catchError,
  of,
} from 'rxjs';
import { environment } from 'src/environments/environment.development';
import { ImageResponse, BlockchainResponse } from '../models/models';
import { AuthService } from './auth.service';

export interface Photo {
  id: string;
  url: string;
  title: string;
}
@Injectable({
  providedIn: 'root',
})
export class PhotoService {
  private readonly apiUrl = environment.apiURL;
  private photos$ = new BehaviorSubject<any[]>([]);

  constructor(private http: HttpClient, private authService: AuthService) {}

  get photos(): Observable<any[]> {
    return this.photos$.asObservable();
  }

  private get authHeaders(): HttpHeaders {
    return new HttpHeaders({
      Authorization: this.authService.authToken,
    });
  }

  uploadAndProcessPhoto(file: File): Observable<BlockchainResponse> {
    const formData = new FormData();
    formData.append('image', file);

    return this.http
      .post<ImageResponse>(`${this.apiUrl}/user/upload-image`, formData, {
        headers: this.authHeaders,
      })
      .pipe(
        switchMap(() => this.processPhotoInBlockchain(formData)),
        switchMap(() => this.mineBlock()),
        switchMap(() => this.getBlockchain()),
        catchError((error) => {
          console.error('Error processing photo:', error);
          return of({ success: false, message: 'Failed to process photo' });
        })
      );
  }

  private processPhotoInBlockchain(
    formData: FormData
  ): Observable<ImageResponse> {
    return this.http.post<ImageResponse>(
      `${this.apiUrl}/blockchain/image/process`,
      formData
    );
  }

  private mineBlock(): Observable<BlockchainResponse> {
    return this.http.get<BlockchainResponse>(`${this.apiUrl}/blockchain/mine`);
  }

  getBlockchain(): Observable<BlockchainResponse> {
    return this.http.get<BlockchainResponse>(`${this.apiUrl}/blockchain/chain`);
  }
}
