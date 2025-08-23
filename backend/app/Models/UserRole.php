<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class UserRole extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'user_roles';

    protected $fillable = [
        'id',
        'user_id',
        'role_id',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];

    public function getUser()
    {
        return $this->hasOne(User::class, 'id', 'user_id')->select('users.*');
    }

    public function getRole()
    {
        return $this->hasMany(Role::class, 'id', 'role_id');
    }
}
