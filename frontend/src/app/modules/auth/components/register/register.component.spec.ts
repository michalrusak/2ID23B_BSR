import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { RouterModule } from '@angular/router';
import { NotifierModule } from 'angular-notifier';
import { MaterialModule } from 'src/app/modules/shared/material/material.module';
import { RegisterComponent } from './register.component';
import { StoreModule } from '@ngrx/store';

describe('RegisterComponent', () => {
  let component: RegisterComponent;
  let fixture: ComponentFixture<RegisterComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [RegisterComponent],
      imports: [
        ReactiveFormsModule,
        HttpClientTestingModule,
        RouterModule.forRoot([]),
        StoreModule.forRoot({}),
        MaterialModule,
        NoopAnimationsModule,
        NotifierModule,
      ],
    });
    fixture = TestBed.createComponent(RegisterComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
