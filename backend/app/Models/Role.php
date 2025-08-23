<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Role extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'role_name',
        'status',
        'created_at',
        'updated_at',
        'deleted_at'
    ];

    public function getPermission()
    {
        return $this->hasMany(RolePermission::class, 'role_id', 'id')
            ->join('permissions', 'permissions.id', '=', 'role_permissions.permission_id')
            ->orderby('sequence_no', 'asc');
    }
}
