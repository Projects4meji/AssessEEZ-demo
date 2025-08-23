<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class RolePermission extends Model
{
    use HasFactory, SoftDeletes;
    protected $table = 'role_permissions';
    
    protected $fillable = [
        'id',
        'role_id',
        'permission_id',
        'status',       
        'created_at',
        'updated_at',
        'deleted_at'
    ];

    public function getRole() {
        return $this->hasMany(Role::class,'id','role_id')
        ->select('roles.*');
    } 

    public function getPermission() {
        return $this->hasMany(Permission::class,'id','permission_id');
    } 
}
