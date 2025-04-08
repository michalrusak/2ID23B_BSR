import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { StoreModule } from '@ngrx/store';
import { EndPoints } from 'src/enums/endPoints.enum';
import { environment } from 'src/environments/environment';
import {
  mockErrorMessage,
  mockLoginBody,
  mockLogoutMessageResponse,
  mockRegisterBody,
  mockRegisterMessageResponse,
  mockResponseUser,
} from 'src/mock-data/mock-data';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let testingController: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, StoreModule.forRoot({})],
      providers: [AuthService],
    });
    service = TestBed.inject(AuthService);
    testingController = TestBed.inject(HttpTestingController);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should user register', (done) => {
    service.register(mockRegisterBody).subscribe((response) => {
      expect(response).toBeTruthy();
      done();
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.register}`
    );
    req.flush(mockRegisterMessageResponse.message);
    expect(req.request.method).toBe('POST');
    testingController.verify();
  });

  it('should handle a failed register', (done) => {
    service.register(mockRegisterBody).subscribe({
      next: () => {
        fail('Expected an error, but got a successful response');
      },
      error: (error) => {
        expect(error.status).toBe(401);
        expect(error.error.message).toEqual(mockErrorMessage);
        done();
      },
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.register}`
    );

    req.flush(
      { message: mockErrorMessage },
      { status: 401, statusText: 'Invalid credentials' }
    );
    testingController.verify();
  });

  it('should user login', (done) => {
    service.login(mockLoginBody).subscribe((response) => {
      expect(response).toBeTruthy();
      done();
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.login}`
    );
    expect(req.request.method).toBe('POST');
    req.flush(mockResponseUser);
    testingController.verify();
  });

  it('should handle a failed login', (done) => {
    service.login(mockLoginBody).subscribe({
      next: () => {
        fail('Expected an error, but got a successful response');
      },
      error: (error) => {
        expect(error.status).toBe(401);
        expect(error.error.message).toEqual(mockErrorMessage);
        done();
      },
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.login}`
    );

    expect(req.request.method).toBe('POST');

    req.flush(
      { message: mockErrorMessage },
      { status: 401, statusText: 'Invalid credentials' }
    );
    testingController.verify();
  });

  it('should user logout', (done) => {
    service.logout().subscribe((response) => {
      expect(response).toBeTruthy();
      done();
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.logout}`
    );

    expect(req.request.method).toBe('GET');
    req.flush(mockLogoutMessageResponse);
    testingController.verify();
  });

  it('should handle a failed logout', (done) => {
    service.logout().subscribe({
      next: () => {
        fail('Expected an error, but got a successful response');
      },
      error: (error) => {
        expect(error.status).toBe(401);
        expect(error.error.message).toEqual(mockErrorMessage);
        done();
      },
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.logout}`
    );

    expect(req.request.method).toBe('GET');
    req.flush(
      { message: mockErrorMessage },
      { status: 401, statusText: 'Invalid credentials' }
    );
    testingController.verify();
  });

  it('should user auto login', (done) => {
    service.autoLogin().subscribe((response) => {
      expect(response).toBeTruthy();
      done();
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.autoLogin}`
    );

    expect(req.request.method).toBe('GET');
    req.flush(mockResponseUser);
    testingController.verify();
  });

  it('should handle a failed auto login', (done) => {
    service.autoLogin().subscribe({
      next: () => {
        fail('Expected an error, but got a successful response');
      },
      error: (error) => {
        expect(error.status).toBe(401);
        expect(error.error.message).toEqual(mockErrorMessage);
        done();
      },
    });

    const req = testingController.expectOne(
      `${environment.apiURL}/${EndPoints.auth}/${EndPoints.autoLogin}`
    );

    expect(req.request.method).toBe('GET');
    req.flush(
      { message: mockErrorMessage },
      { status: 401, statusText: 'Invalid credentials' }
    );
    testingController.verify();
  });
});
