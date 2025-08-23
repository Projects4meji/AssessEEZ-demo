<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Permission extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'permissions';

    protected $fillable = [
        'id',
        'permission_name',
        'status',
        'created_at',
        'updated_at',
        'path',
        'icon',
        'sequence_no',
        'deleted_at'
    ];

    public function getPermissionType()
    {
        return $this->hasMany(PermissionPermissionType::class, 'permission_id', 'id')
            ->select('permission_permission_types.*');
    }

    public function getPrm()
    {
        return $this->hasMany(RolePermission::class, 'role_id', 'permission_id');
    }
}
