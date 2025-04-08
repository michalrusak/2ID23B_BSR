import { Component } from '@angular/core';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { AuthService } from 'src/app/modules/core/services/auth.service';
import { RouterEnum } from 'src/enums/router.enum';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
})
export class LoginComponent {
  RouterEnum = RouterEnum;

  form = new FormGroup({
    username: new FormControl('', {
      validators: [
        Validators.required,
        Validators.minLength(3),
        Validators.maxLength(30),
      ],
      nonNullable: true,
    }),
    password: new FormControl('', {
      validators: [
        Validators.required,
        Validators.minLength(8),
        Validators.maxLength(30),
      ],
      nonNullable: true,
    }),
  });

  constructor(private authService: AuthService, private router: Router) {}

  get controls() {
    return this.form.controls;
  }

  getErrorMessage(control: FormControl) {
    if (control.hasError('required')) {
      return 'This field is required';
    }
    if (control.hasError('minlength')) {
      return 'Not enough characters';
    }
    if (control.hasError('maxlength')) {
      return 'Too many characters';
    }
    return '';
  }

  onSubmit() {
    if (this.form.valid) {
      const { username, password } = this.form.value;
      if (username && password) {
        this.authService.login(username, password).subscribe(
          () => {
            this.form.reset();
            this.router.navigate([RouterEnum.addPhoto]);
          },
          (error) => {
            console.error(error);
          }
        );
      }
    }
  }
}
