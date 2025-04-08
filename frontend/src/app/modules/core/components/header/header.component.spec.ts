import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HeaderComponent } from './header.component';
import { StoreModule } from '@ngrx/store';
import { MaterialModule } from 'src/app/modules/shared/material/material.module';
import { RouterModule } from '@angular/router';

describe('HeaderComponent', () => {
  let component: HeaderComponent;
  let fixture: ComponentFixture<HeaderComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [HeaderComponent],
      imports: [
        StoreModule.forRoot({}),
        RouterModule.forRoot([]),
        MaterialModule,
      ],
    });
    fixture = TestBed.createComponent(HeaderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
