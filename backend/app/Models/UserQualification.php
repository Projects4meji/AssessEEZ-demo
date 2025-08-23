<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class UserQualification extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'user_id',
        'qualification_id',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at',
        'id',
        'first_name',
        'middle_name',
        'sur_name',
        'role_id',
        'ref_number',
        'avatar',
        'contact',
        'date_of_birth',
        'cohort_batch_no',
        'date_of_registration',
        'sampling_ratio',
        'view_only_id',
        'learner_number',
        'location',
        'country',
        'city',
        'lat',
        'lon',
        'status',        
        'email',
        'email_verified_at',
        'password',
        'remember_token',   
        'expiry_date',
        'code',
        'disability'
    ];

    public function user()
    {
        return $this->hasOne(User::class, 'id', 'user_id');
    }
}
