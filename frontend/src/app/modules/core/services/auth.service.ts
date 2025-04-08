import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, of, tap } from 'rxjs';
import { environment } from 'src/environments/environment.development';
import { User, ResponseUser } from '../models/models';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly apiUrl = environment.apiURL;
  private readonly tokenKey = 'auth_token';
  private currentUserSubject = new BehaviorSubject<String | null>(null);

  constructor(private http: HttpClient) {
    const token = localStorage.getItem(this.tokenKey);
    if (token) {
      this.validateToken();
    }
  }

  get currentUser$(): Observable<String | null> {
    return this.currentUserSubject.asObservable();
  }

  get token(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  // Modified to return the complete Bearer token
  get authToken(): string {
    return `Bearer ${this.token}`;
  }

  register(username: string, password: string): Observable<ResponseUser> {
    return this.http.post<ResponseUser>(`${this.apiUrl}/user/register`, {
      username,
      password,
    });
  }

  login(username: string, password: string): Observable<ResponseUser> {
    return this.http
      .post<ResponseUser>(`${this.apiUrl}/user/login`, {
        username,
        password,
      })
      .pipe(
        tap((response) => {
          if (response.token) {
            localStorage.setItem(this.tokenKey, response.token);
            this.currentUserSubject.next(response.username);
          }
        })
      );
  }

  logout(): Observable<void> {
    localStorage.removeItem(this.tokenKey);
    this.currentUserSubject.next(null);
    return of(void 0);
  }

  private validateToken(): void {
    // Add token validation logic here if needed
  }
}
